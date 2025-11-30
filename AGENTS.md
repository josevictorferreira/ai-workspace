# Agent Guidelines

## commands
- **Start**: `docker-compose up` (add `-d` for detached)
- **Stop**: `docker-compose down`
- **Validate**: `docker-compose config` (checks YAML syntax/validity)
- **Logs**: `docker-compose logs -f invokeai`

## Code Style & Structure
- **Repository Type**: Infrastructure/Configuration (Docker + YAML).
- **Formatting**:
  - **YAML**: Strict 2-space indentation.
  - **Shell**: Standard POSIX sh compatibility where possible.
- **Conventions**:
  - **Volumes**: Use relative paths (`./data`). For rootless Podman/Docker, use `:Z,U` flags for permissions.
  - **Environment**: Prefer `.env` for secrets/variables over hardcoding in `docker-compose.yml`.

## Testing
- **Manual**: Start the container and verify "Invoke running on http://..." in logs.
- **Health Check**: `curl -f http://localhost:9090/health` (if exposed) or check container status.
