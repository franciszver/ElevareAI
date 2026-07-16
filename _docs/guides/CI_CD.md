# CI/CD Pipeline Documentation

## Overview

The AI Study Companion uses GitHub Actions for continuous integration and deployment.

---

## 🔄 **CI Pipeline**

### **Workflow: `ci.yml`**

Runs on every push and pull request to `main` and `develop` branches.

#### **Jobs:**

1. **Test Job**
   - Runs all unit and integration tests
   - Uses PostgreSQL service container
   - Generates coverage reports
   - Uploads coverage to Codecov

2. **Lint Job**
   - Checks code formatting with Black
   - Validates import sorting with isort
   - Runs flake8 for code quality
   - Type checking with mypy

3. **Security Job**
   - Scans dependencies for vulnerabilities
   - Uses Safety to check requirements.txt

---

## 🚀 **CD Pipeline**

### **Workflow: `deploy.yml`**

Runs on pushes to `main` and version tags.

#### **Jobs:**

1. **Build and Push**
   - Builds Docker image
   - Pushes to GitHub Container Registry
   - Tags images with branch, SHA, and version

2. **Deploy Staging**
   - Triggers on pushes to `develop`
   - Deploys to staging environment

3. **Deploy Production**
   - Triggers on version tags (v*)
   - Deploys to production environment

---

## 📋 **Required Secrets**

Configure these secrets in GitHub repository settings:

### **CI Secrets:**
- `OPENROUTER_API_KEY` - OpenRouter API key for tests
- `API_KEY` - Service API key

### **CD Secrets:**
- `GITHUB_TOKEN` - Automatically provided by GitHub Actions
- Additional deployment secrets as needed (AWS credentials, etc.)

---

## 🔧 **Local Testing**

### **Run CI Checks Locally**

```bash
# Install dependencies
pip install -r requirements.txt
pip install black flake8 isort mypy safety

# Run tests
pytest tests/ -v --cov=src

# Check formatting
black --check src tests

# Check imports
isort --check-only src tests

# Lint
flake8 src tests

# Type check
mypy src

# Security check
safety check --file requirements.txt
```

---

## 📊 **Code Coverage**

Coverage reports are generated and uploaded to Codecov on every CI run.

View coverage at: https://codecov.io/gh/[your-org]/PennyGadget

---

## 🎯 **Branch Strategy**

- **`main`** - Production-ready code
- **`develop`** - Development branch
- **Feature branches** - `feature/description`
- **Hotfix branches** - `hotfix/description`

---

## 🏷️ **Versioning**

Version tags follow semantic versioning:
- `v1.0.0` - Major release
- `v1.1.0` - Minor release
- `v1.1.1` - Patch release

---

## 🔍 **Code Quality Gates**

PRs must pass:
- ✅ All tests
- ✅ Code formatting (Black)
- ✅ Import sorting (isort)
- ✅ Linting (flake8)
- ✅ Type checking (mypy)
- ✅ Security scan (safety)

---

## 🚨 **Failure Handling**

### **Test Failures**
- PRs with failing tests cannot be merged
- Review test output in Actions tab
- Fix issues and push again

### **Lint Failures**
- Auto-fix with: `black src tests && isort src tests`
- Commit and push fixes

### **Security Issues**
- Review security scan results
- Update vulnerable dependencies
- Re-run security check

---

## 📝 **Pull Request Process**

1. Create feature branch
2. Make changes
3. Run local checks
4. Push to GitHub
5. Create PR (template will guide you)
6. CI runs automatically
7. Address any failures
8. Get code review approval
9. Merge to `develop` or `main`

---

## 🎉 **Deployment Process**

### **Staging Deployment**
- Push to `develop` branch
- Automatic deployment to staging
- Verify in staging environment

### **Production Deployment**
- Create version tag: `git tag v1.0.0`
- Push tag: `git push origin v1.0.0`
- Automatic deployment to production
- Verify in production environment

---

## 🔐 **Security**

- Secrets are encrypted and stored securely
- Never commit secrets to repository
- Use GitHub Secrets for sensitive data
- Regular security scans in CI

---

## 📚 **Additional Resources**

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Buildx](https://docs.docker.com/buildx/)
- [Codecov](https://docs.codecov.com/)

---

**Last Updated**: November 2024

