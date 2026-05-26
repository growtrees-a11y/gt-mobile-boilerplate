# Terraform — Mobile Telemetry Infrastructure
#
# Path B: API Gateway + Lambda + DynamoDB (serverless)
#
# Usage:
#   terraform init && terraform plan && terraform apply
#

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "proj-07-mobile-telemetry"
}

variable "environment" {
  type    = string
  default = "production"
}

locals {
  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# ─── DynamoDB Table ──────────────────────────────────────────────

resource "aws_dynamodb_table" "telemetry_events" {
  name         = "${var.project_name}-events"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "device_id"
  range_key    = "timestamp"

  attribute {
    name = "device_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = local.tags
}

# ─── Lambda Function ─────────────────────────────────────────────

resource "aws_iam_role" "lambda_exec" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      },
    ]
  })

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "telemetry_ingest" {
  function_name = "${var.project_name}-ingest"
  handler       = "lambda_handler.lambda_handler"
  runtime       = "python3.11"
  role          = aws_iam_role.lambda_exec.arn
  timeout       = 30
  memory_size   = 256

  filename         = data.archive_file.lambda_archive.output_path
  source_code_hash = data.archive_file.lambda_archive.output_base64sha256

  environment {
    variables = {
      TELEMETRY_TABLE = aws_dynamodb_table.telemetry_events.name
    }
  }

  tags = local.tags
}

resource "aws_lambda_function" "batch_ingest" {
  function_name = "${var.project_name}-batch"
  handler       = "lambda_handler.lambda_handler"
  runtime       = "python3.11"
  role          = aws_iam_role.lambda_exec.arn
  timeout       = 60
  memory_size   = 512

  filename         = data.archive_file.lambda_archive.output_path
  source_code_hash = data.archive_file.lambda_archive.output_base64sha256

  environment {
    variables = {
      TELEMETRY_TABLE = aws_dynamodb_table.telemetry_events.name
    }
  }

  tags = local.tags
}

# ─── API Gateway ─────────────────────────────────────────────────

resource "aws_apigatewayv2_api" "telemetry" {
  name   = "${var.project_name}-api"
  protocol_type = "HTTP"

  tags = local.tags
}

resource "aws_apigatewayv2_integration" "ingest_integration" {
  api_id             = aws_apigatewayv2_api.telemetry.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.telemetry_ingest.invoke_arn
  integration_method = "POST"
}

resource "aws_apigatewayv2_route" "ingest_route" {
  api_id    = aws_apigatewayv2_api.telemetry.id
  route_key = "POST /telemetry"
  target    = "integrations/${aws_apigatewayv2_integration.ingest_integration.id}"
}

resource "aws_apigatewayv2_integration" "batch_integration" {
  api_id             = aws_apigatewayv2_api.telemetry.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.batch_ingest.invoke_arn
  integration_method = "POST"
}

resource "aws_apigatewayv2_route" "batch_route" {
  api_id    = aws_apigatewayv2_api.telemetry.id
  route_key = "POST /telemetry/batch"
  target    = "integrations/${aws_apigatewayv2_integration.batch_integration.id}"
}

resource "aws_apigatewayv2_stage" "prod" {
  api_id      = aws_apigatewayv2_api.telemetry.id
  name        = "prod"
  auto_deploy = true

  tags = local.tags
}

# ─── Lambda Permissions ──────────────────────────────────────────

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.telemetry_ingest.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${aws_apigatewayv2_api.telemetry.execution_arn}/*/*"
}

# ─── DynamoDB IAM Policy ────────────────────────────────────────

resource "aws_iam_policy" "dynamodb_write" {
  name        = "${var.project_name}-dynamodb-write"
  description = "Allow Lambda to write telemetry events to DynamoDB"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:BatchWriteItem",
          "dynamodb:DescribeTable",
        ]
        Resource = aws_dynamodb_table.telemetry_events.arn
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "dynamodb_write" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.dynamodb_write.arn
}

# ─── Data Sources ────────────────────────────────────────────────

data "archive_file" "lambda_archive" {
  type        = "zip"
  source_dir  = "${path.module}/.."
  output_path = "${path.module}/../lambda.zip"
}

# ─── Outputs ──────────────────────────────────────────────────────

output "api_endpoint" {
  description = "API Gateway endpoint URL"
  value       = "${aws_apigatewayv2_api.telemetry.api_endpoint}/prod"
}

output "dynamodb_table" {
  description = "DynamoDB table name"
  value       = aws_dynamodb_table.telemetry_events.name
}
