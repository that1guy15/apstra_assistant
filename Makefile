# Makefile

# Variables
REPO_URL = 983186512003.dkr.ecr.us-east-2.amazonaws.com/apstra_assistant
REGION = us-east-2
COMMIT_HASH = $(shell git rev-parse HEAD)
IMAGE_NAME = lambda_apstra_assistant

# Build Docker image
build:
	docker build -t $(IMAGE_NAME):$(COMMIT_HASH) .

# Tag Docker image
tag:
	docker tag $(IMAGE_NAME):$(COMMIT_HASH) $(REPO_URL):$(COMMIT_HASH)

# Login to ECR
ecr-login:
	aws ecr get-login-password --region $(REGION) | docker login --username AWS --password-stdin $(REPO_URL)

# Push Docker image to ECR
push: build tag ecr-login
	docker push $(REPO_URL):$(COMMIT_HASH)

# Clean up local Docker images
clean:
	docker rmi $(IMAGE_NAME):$(COMMIT_HASH)
	docker rmi $(REPO_URL):$(COMMIT_HASH)

# Full pipeline: build, tag, login, push
all: build tag ecr-login push

.PHONY: build tag ecr-login push clean all
