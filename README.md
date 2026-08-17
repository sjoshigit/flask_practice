# Student Registration System — CI/CD Pipeline & Architecture

A simple **Flask** web application for managing student records with **MongoDB** as the backend database. The application is automated through an end-to-end CI/CD pipeline using **Docker, Amazon ECR, Amazon EC2, and GitHub Actions**.

---

## 📋 Table of Contents

- [Prerequisites & AWS Infrastructure](#1-prerequisites--aws-infrastructure)
- [GitHub Secrets Configuration](#2-github-secrets-configuration)
- [CI/CD Deployment Architecture](#3-cicd-deployment-architecture)
- [EC2 Deployment Method](#4-ec2-deployment-method--rationale)
- [Manual Deployment & Recovery](#5-manual-deployment--recovery)
- [Local Development Setup](#6-local-development-setup)
- [Project Structure](#7-project-structure)
- [Deployment Verification](#8-deployment-verification-checklist)
- [Troubleshooting](#9-troubleshooting)
- [Security Considerations](#10-security-considerations)
- [License](#license)

---

## 1. Prerequisites & AWS Infrastructure

### A. AWS Resources

The following resources are required:

| Resource | Configuration |
|---|---|
| **Amazon ECR** | Private repository named `flask-app-sjoshi` in `ap-south-1` |
| **Amazon EC2** | Ubuntu 22.04/24.04 LTS, preferably `t3.micro`, with public IPv4 |
| **MongoDB Atlas** | Active MongoDB cluster accessible from the EC2 instance |

> **Security recommendation:** Avoid `0.0.0.0/0` for MongoDB Atlas in production. Restrict Network Access to required IP addresses whenever possible.

### B. EC2 System Setup

SSH into the EC2 instance and install Docker and AWS CLI:

```bash
sudo apt update -y
sudo apt install -y docker.io awscli

sudo systemctl enable --now docker

sudo usermod -aG docker ubuntu
```

Log out and reconnect after adding `ubuntu` to the Docker group.

Verify the installation:

```bash
docker --version
aws --version
```

### C. IAM Roles & Permissions

#### EC2 Instance Role

Attach an IAM role with:

- `AmazonEC2ContainerRegistryReadOnly`

This allows EC2 to pull images from Amazon ECR without storing AWS credentials on the server.

#### CI/CD IAM Identity

The GitHub Actions workflow requires permissions to authenticate with and push images to Amazon ECR.

For a simplified assignment setup:

- `AmazonEC2ContainerRegistryPowerUser`

> **Production recommendation:** Use a least-privilege IAM policy and GitHub OIDC instead of long-lived AWS access keys.

### D. Security Group Rules

| Direction | Port | Protocol | Source | Purpose |
|---|---:|---|---|---|
| Inbound | `22` | TCP | Restricted IP/runner access | SSH administration/deployment |
| Inbound | `5000` | TCP | Required clients | Flask application and health checks |
| Outbound | All | All | `0.0.0.0/0` | AWS, package, and MongoDB connectivity |

> **Security recommendation:** Restrict SSH access to trusted IP addresses. Avoid exposing port `5000` publicly in production.

---

## 2. GitHub Secrets Configuration

Navigate to:

**GitHub Repository → Settings → Secrets and variables → Actions**

Add the following repository secrets:

| Secret | Description |
|---|---|
| `AWS_ACCESS_KEY_ID` | Access key ID for the CI/CD IAM identity |
| `AWS_SECRET_ACCESS_KEY` | Secret access key for the CI/CD IAM identity |
| `EC2_HOST` | Public IPv4 address or hostname of the EC2 instance |
| `EC2_USER` | EC2 SSH user, typically `ubuntu` |
| `EC2_SSH_KEY` | Complete contents of the EC2 private `.pem` key |
| `MONGO_URI` | MongoDB Atlas connection string |
| `SMTP_SERVER` | SMTP server hostname, e.g. `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port, typically `465` or `587` |
| `SMTP_USERNAME` | Authenticated SMTP account |
| `SMTP_PASSWORD` | SMTP/app-specific authentication password |
| `NOTIFICATION_EMAIL` | Email address receiving deployment notifications |

Example MongoDB URI:

```text
mongodb+srv://<username>:<password>@cluster0.mongodb.net/student_db?retryWrites=true&w=majority
```

### 🔐 Secret Management Guidelines

- Never commit credentials to Git.
- Never place production secrets directly in the Dockerfile.
- Never print secrets in GitHub Actions logs.
- Rotate credentials if they are accidentally exposed.
- For production, prefer GitHub OIDC with AWS IAM roles.

---

## 3. CI/CD Deployment Architecture

```text
┌──────────────┐
│  Developer   │
└──────┬───────┘
       │ git push
       ▼
┌──────────────────┐
│ GitHub Repository│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ GitHub Actions   │
│                  │
│ • Run tests      │
│ • Build image    │
│ • Login to ECR   │
│ • Push image     │
│ • SSH to EC2     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   Amazon ECR     │
│ Docker Registry  │
└────────┬─────────┘
         │ docker pull
         ▼
┌──────────────────┐
│   Amazon EC2     │
│                  │
│ • Docker         │
│ • Flask container│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ MongoDB Atlas    │
└──────────────────┘
```

### Deployment Flow

1. Developer pushes code to GitHub.
2. GitHub Actions starts the CI/CD workflow.
3. Automated tests are executed.
4. A Docker image is built.
5. GitHub Actions authenticates with Amazon ECR.
6. The image is tagged using the commit SHA.
7. The image is pushed to ECR.
8. GitHub Actions connects to EC2 through SSH.
9. EC2 authenticates with ECR.
10. EC2 pulls the new image.
11. The previous container is stopped and removed.
12. The new container starts with `--restart unless-stopped`.
13. The `/health` endpoint is checked.
14. Deployment notification is sent when configured.

---

## 4. EC2 Deployment Method & Rationale

### Connection Method

The deployment uses **SSH** through the `appleboy/ssh-action` GitHub Action.

The workflow connects using:

- `EC2_HOST`
- `EC2_USER`
- `EC2_SSH_KEY`

Deployment commands are then executed directly on the EC2 instance.

### Why SSH Was Selected

SSH was selected because this project uses a standalone EC2 instance and requires a simple deployment mechanism.

**Advantages:**

- Simple architecture
- Direct Docker command execution
- Easy troubleshooting
- No additional SSM configuration
- Straightforward manual recovery

### SSH vs. SSM

| Feature | SSH | AWS SSM |
|---|---|---|
| Setup complexity | Low | Medium |
| Direct EC2 access | Yes | No direct SSH required |
| IAM integration | Limited | Strong |
| Centralized access control | Basic | Strong |
| Auditability | Basic | Better |
| Suitable for this assignment | ✅ Yes | Optional |

> **Production recommendation:** AWS Systems Manager (SSM) is preferable for larger environments because it can eliminate direct SSH exposure and provide centralized access control and auditing.

---

## 5. Manual Deployment & Recovery

If GitHub Actions becomes unavailable, the application can be deployed manually by building the Docker image, pushing it to ECR, and restarting the container on EC2.

### Step 1 — Authenticate Docker with ECR

Run locally:

```bash
aws ecr get-login-password --region ap-south-1 \
  | docker login \
  --username AWS \
  --password-stdin <AWS_ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com
```

### Step 2 — Build the Docker Image

Replace `<COMMIT_SHA>` with the desired Git commit SHA:

```bash
docker build \
  -t <AWS_ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/flask-app-sjoshi:<COMMIT_SHA> .
```

### Step 3 — Push the Image to ECR

```bash
docker push \
  <AWS_ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/flask-app-sjoshi:<COMMIT_SHA>
```

### Step 4 — Connect to EC2

```bash
ssh -i /path/to/key.pem ubuntu@<EC2_PUBLIC_IP>
```

### Step 5 — Authenticate EC2 with ECR

```bash
aws ecr get-login-password --region ap-south-1 \
  | docker login \
  --username AWS \
  --password-stdin <AWS_ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com
```

### Step 6 — Pull the Required Image

```bash
docker pull \
  <AWS_ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/flask-app-sjoshi:<COMMIT_SHA>
```

### Step 7 — Stop and Remove the Existing Container

```bash
docker stop flask_app || true
docker rm flask_app || true
```

### Step 8 — Start the Updated Container

```bash
docker run -d \
  --name flask_app \
  --restart unless-stopped \
  -p 5000:5000 \
  -e MONGO_URI="<YOUR_MONGO_URI>" \
  <AWS_ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/flask-app-sjoshi:<COMMIT_SHA>
```

### Step 9 — Verify the Deployment

```bash
docker ps
```

```bash
docker logs flask_app
```

```bash
curl --fail http://localhost:5000/health
```

A successful health-check response confirms that the container and Flask application are running.

---

## 6. Local Development Setup

### Step 1 — Clone the Repository

```bash
git clone https://github.com/sjoshigit/flask_practice.git
cd flask_practice
```

### Step 2 — Create a Virtual Environment

```bash
python -m venv venv
```

**Linux/macOS:**

```bash
source venv/bin/activate
```

**Windows:**

```powershell
venv\Scripts\activate
```

### Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
pip install pytest
```

### Step 4 — Configure Environment Variables

Create `.env` in the project root:

```env
MONGO_URI=mongodb+srv://<username>:<password>@cluster0.mongodb.net/student_db?retryWrites=true&w=majority
```

> Do not commit `.env` to Git.

### Step 5 — Run Tests

```bash
pytest
```

### Step 6 — Run the Application

```bash
python app.py
```

---

## 7. Project Structure

```text
flask_practice/
│
├── .github/
│   └── workflows/
│       └── ci-cd.yml              # GitHub Actions CI/CD pipeline
│
├── templates/
│   ├── base.html                  # Base template
│   ├── index.html                 # Student listing
│   ├── add_student.html           # Add student form
│   └── update_student.html        # Update student form
│
├── app.py                         # Flask application & /health endpoint
├── test_app.py                    # Pytest test suite
├── Dockerfile                     # Docker image definition
├── .dockerignore                  # Docker build exclusions
├── .env.example                   # Environment variable template
├── requirements.txt               # Python dependencies
└── README.md                      # Project documentation
```

---

## 8. Deployment Verification Checklist

After deployment, verify:

- [ ] GitHub Actions workflow completed successfully.
- [ ] Automated tests passed.
- [ ] Docker image was built successfully.
- [ ] Image was pushed to Amazon ECR.
- [ ] EC2 authenticated successfully with ECR.
- [ ] Latest image was pulled.
- [ ] Previous container was stopped and removed.
- [ ] New `flask_app` container is running.
- [ ] Restart policy is configured.
- [ ] `/health` endpoint responds successfully.
- [ ] Flask can connect to MongoDB Atlas.
- [ ] Application is accessible through the configured port.
- [ ] Deployment notification was received, if enabled.

---

## 9. Troubleshooting

### Check Container Status

```bash
docker ps -a
```

### View Application Logs

```bash
docker logs flask_app
```

### Follow Logs in Real Time

```bash
docker logs -f flask_app
```

### Check Port Availability

```bash
sudo ss -tulpn | grep 5000
```

### Test Application Locally on EC2

```bash
curl http://localhost:5000/health
```

### Check AWS Identity

```bash
aws sts get-caller-identity
```

If this command fails, verify that the EC2 IAM role and AWS CLI configuration are correct.

### Check ECR Images

```bash
aws ecr describe-images \
  --repository-name flask-app-sjoshi \
  --region ap-south-1
```

---

## 10. Security Considerations

For an academic or demonstration deployment, the configuration above provides a straightforward implementation.

For production environments, consider:

1. Replace long-lived AWS access keys with **GitHub Actions OIDC**.
2. Apply least-privilege IAM policies.
3. Restrict EC2 SSH access to trusted IP addresses.
4. Avoid exposing port `5000` directly to the internet.
5. Place Nginx or an Application Load Balancer in front of Flask.
6. Restrict MongoDB Atlas Network Access.
7. Store production secrets in **AWS Secrets Manager** or **AWS Systems Manager Parameter Store**.
8. Enable HTTPS for public application traffic.
9. Rotate credentials regularly.
10. Never commit `.env`, private SSH keys, or AWS credentials to Git.

---

## License

This project is licensed under the **MIT License**.
