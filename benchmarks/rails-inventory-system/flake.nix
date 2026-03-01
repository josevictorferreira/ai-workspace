{
  description = "Ruby on Rails with PostgreSQL development environment";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    dev-sandbox.url = "github:josevictorferreira/dev-sandbox";
    dev-sandbox.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs =
    {
      nixpkgs,
      flake-utils,
      dev-sandbox,
      ...
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
        # dev-sandbox.lib is a function that takes system
        sandbox = dev-sandbox.lib { inherit system; };

        postgresVersion = pkgs.postgresql_18.withPackages (ps: [ ps.postgis ]);

        # Project-specific helper scripts
        db_reset = pkgs.writeShellScriptBin "db_reset" ''
          bundle exec rails db:drop
          bundle exec rails db:create
          bundle exec rails db:migrate
        '';

        db_parallel_create = pkgs.writeShellScriptBin "db_parallel_create" ''
          echo "Creating parallel test databases on port $PGPORT..."
          for i in $(seq 2 $(($(nproc) + 1))); do
            createdb -h "$PGHOST" -p "$PGPORT" -U postgres "valoris_test$i" 2>/dev/null || true
          done
          echo "Parallel test databases ready"
        '';

        db_parallel_drop = pkgs.writeShellScriptBin "db_parallel_drop" ''
          echo "Dropping parallel test databases on port $PGPORT..."
          for i in $(seq 2 $(($(nproc) + 1))); do
            dropdb -h "$PGHOST" -p "$PGPORT" -U postgres "valoris_test$i" 2>/dev/null || true
          done
          echo "Parallel test databases dropped"
        '';

        db_use_homelab = pkgs.writeShellScriptBin "db_use_homelab" ''
          set -e
          DB_PASSWORD_FILE="/run/secrets/valoris_database_password"
          SECRET_KEY_FILE="/run/secrets/valoris_secret_key_base"

          if [ ! -f "$DB_PASSWORD_FILE" ]; then
            echo "Error: $DB_PASSWORD_FILE not found" >&2
            exit 1
          fi
          if [ ! -f "$SECRET_KEY_FILE" ]; then
            echo "Error: $SECRET_KEY_FILE not found" >&2
            exit 1
          fi

          DB_PASSWORD=$(cat "$DB_PASSWORD_FILE")
          SECRET_KEY_BASE=$(cat "$SECRET_KEY_FILE")

          echo "unset DATABASE_URL"
          echo "export VALORIS_DATABASE_HOST=\"10.10.10.133\""
          echo "export VALORIS_DATABASE_PORT=\"5432\""
          echo "export VALORIS_DATABASE_USERNAME=\"postgres\""
          echo "export VALORIS_DATABASE_PASSWORD=\"$DB_PASSWORD\""
          echo "export SECRET_KEY_BASE=\"$SECRET_KEY_BASE\""
          echo "export RAILS_ENV=production"
        '';

        db_homelab = pkgs.writeShellScriptBin "db_homelab" ''
          # Shell function for eval-ing to connect to homelab production database
          # Usage: eval "$(db_homelab)"
          # Requires HOMELAB_POSTGRES_USERNAME, HOMELAB_POSTGRES_PASSWORD, and VALORIS_SECRET_KEY env vars

          if [ -z "''${HOMELAB_POSTGRES_USERNAME:-}" ]; then
            echo "# Error: HOMELAB_POSTGRES_USERNAME is not set" >&2
            exit 1
          fi

          if [ -z "''${HOMELAB_POSTGRES_PASSWORD:-}" ]; then
            echo "# Error: HOMELAB_POSTGRES_PASSWORD is not set" >&2
            exit 1
          fi

          if [ -z "''${VALORIS_SECRET_KEY:-}" ]; then
            echo "# Error: VALORIS_SECRET_KEY is not set" >&2
            exit 1
          fi

          echo "unset DATABASE_URL"
          echo "export VALORIS_DATABASE_HOST=\"10.10.10.133\""
          echo "export VALORIS_DATABASE_PORT=\"5432\""
          echo "export VALORIS_DATABASE_USERNAME=\"$HOMELAB_POSTGRES_USERNAME\""
          echo "export VALORIS_DATABASE_PASSWORD=\"$HOMELAB_POSTGRES_PASSWORD\""
          echo "export SECRET_KEY_BASE=\"$VALORIS_SECRET_KEY\""
          echo "export RAILS_ENV=production"
          echo "# Homelab database configured - run 'rails console' to connect"
        '';

        db_use_local = pkgs.writeShellScriptBin "db_use_local" ''
          echo "export DATABASE_URL=\"postgresql://postgres:postgres@localhost:$PGPORT/development?host=$PGHOST\""
          echo "export VALORIS_DATABASE_HOST=\"$PGHOST\""
          echo "export VALORIS_DATABASE_PORT=\"$PGPORT\""
          echo "export VALORIS_DATABASE_USERNAME=\"postgres\""
          echo "export VALORIS_DATABASE_PASSWORD=\"postgres\""
          echo "export RAILS_ENV=development"
        '';

        db_setup = pkgs.writeShellScriptBin "db_setup" ''
          set -e
          echo "=== Setting up database ==="
          db_start
          bundle exec rails db:create 2>/dev/null || true
          bundle exec rails db:migrate
          echo "=== Database ready ==="
        '';

        # Create a git worktree and start a fully initialized sandbox
        sandboxWorktree = pkgs.writeShellScriptBin "sandbox-worktree" ''
          set -e
          BRANCH="''${1?Usage: sandbox-worktree <branch-name> [worktree-path] [subpath]}"
          PROJECT_NAME=$(basename "$PWD")
          WORKTREE_PATH="''${2:-$PWD/../$PROJECT_NAME-$BRANCH}"
          SUBPATH="$3"

          if ! git rev-parse --git-dir > /dev/null 2>&1; then
            echo "Error: Not in a git repository"
            exit 1
          fi

          git worktree prune

          if [ -d "$WORKTREE_PATH" ]; then
            WORKTREE_ABS=$(cd "$WORKTREE_PATH" && pwd)
            echo "=== Entering Existing Worktree: $WORKTREE_ABS ==="
            cd "$WORKTREE_ABS"
          else
            if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
              git worktree add "$WORKTREE_PATH" "$BRANCH"
            elif git show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; then
              git worktree add "$WORKTREE_PATH" -b "$BRANCH" "origin/$BRANCH"
            else
              git worktree add "$WORKTREE_PATH" -b "$BRANCH"
            fi
            WORKTREE_ABS=$(cd "$WORKTREE_PATH" && pwd)
            cd "$WORKTREE_ABS"
          fi

          if [ -n "$SUBPATH" ]; then
            exec nix develop --impure --command zsh -ic "db_start; cd \"$SUBPATH\" && exec zsh"
          else
            exec nix develop --impure --command zsh -ic "db_start; exec zsh -c \"cd backend && bundle exec rails db:create && bundle exec rails db:migrate\"; exec zsh"
          fi
        '';

        sandboxWorktreeList = pkgs.writeShellScriptBin "sandbox-worktree-list" ''
          git worktree list
        '';

        sandboxFinish = pkgs.writeShellScriptBin "sandbox-finish" ''
          set -e
          SQUASH=true
          [[ "$*" == *"--no-squash"* ]] && SQUASH=false

          CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
          MAIN_WORKTREE=$(git worktree list --porcelain | head -1 | cut -d' ' -f2)
          CURRENT_WORKTREE=$(git rev-parse --show-toplevel)

          if [ "$CURRENT_WORKTREE" = "$MAIN_WORKTREE" ]; then
            echo "Error: Already in the main worktree."
            exit 1
          fi

          sandbox-down 2>/dev/null || true
          cd "$MAIN_WORKTREE"

          DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")
          git checkout "$DEFAULT_BRANCH"

          if [ "$SQUASH" = true ]; then
            git merge --squash "$CURRENT_BRANCH"
          else
            git merge "$CURRENT_BRANCH" --no-edit
          fi

          git worktree remove "$CURRENT_WORKTREE" --force
          exec zsh
        '';

        browserPackages =
          if pkgs.stdenv.isLinux then
            [
              pkgs.chromium
              pkgs.chromedriver
            ]
          else
            [ ];
        browserEnvVars =
          if pkgs.stdenv.isLinux then
            ''
              export CHROME_BIN=${pkgs.chromium}/bin/chromium
              export CHROMEDRIVER_BIN=${pkgs.chromedriver}/bin/chromedriver
            ''
          else
            ''
              export CHROME_BIN="''${CHROME_BIN:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
              export CHROMEDRIVER_BIN="''${CHROMEDRIVER_BIN:-$(which chromedriver 2>/dev/null || echo chromedriver)}"
            '';

        # swagger-cli built from npm using buildNpmPackage
        swaggerCli = pkgs.buildNpmPackage rec {
          pname = "swagger-cli";
          version = "4.0.4";

          src = pkgs.fetchFromGitHub {
            owner = "APIDevTools";
            repo = "swagger-cli";
            rev = "v${version}";
            hash = "sha256-WgzfSd57vRwa1HrSgNxD0F5ckczBkOaVmrEZ9tMAcRA=";
          };

          npmDepsHash = "sha256-go9eYGCZmbwRArHVTVa6mxL+kjvBcrLxKw2iVv0a5hY=";

          # Skip npm build - package has no build step
          dontNpmBuild = true;

          meta = {
            description = "Swagger 2.0 and OpenAPI 3.0 command-line tool";
            homepage = "https://apitools.dev/swagger-cli/";
            license = pkgs.lib.licenses.mit;
          };
        };

        # Build the sandbox using dev-sandbox lib
        devSandbox = sandbox.mkSandbox {
          projectRoot = ./.;
          postgresVersion = postgresVersion;
          packages =
            with pkgs;
            [
              watchman
              ruby
              bundler
              libyaml
              zlib
              openssl
              readline
              gnumake
              gcc
              pkg-config
              libiconv
              podman
              crane
              # Project scripts
              db_reset
              db_parallel_create
              db_parallel_drop
              db_use_homelab
              db_homelab
              db_use_local
              db_setup
              sandboxWorktree
              sandboxWorktreeList
              sandboxFinish
              swaggerCli
            ]
            ++ browserPackages;

          env = {
            BUNDLE_PATH = "./.bundle";
            GEM_HOME = "./.bundle";
            RUBY_YJIT_ENABLE = "1";
          };

          shellHook = ''
            export PATH="$PWD/.bundle/bin:$PATH"
            ${browserEnvVars}

            # Rails DB configuration defaults (using sandbox exports)
            # We force these to follow PGPORT/PGHOST to ensure the local sandbox is used by default.
            # Stale environment variables from parent shells or homelab scripts are overridden here.
            export VALORIS_DATABASE_HOST="$PGHOST"
            export VALORIS_DATABASE_PORT="$PGPORT"
            export VALORIS_DATABASE_USERNAME="postgres"
            export VALORIS_DATABASE_PASSWORD="postgres"

            echo "=== Valoris Sandbox Ready ==="
            echo "Ruby: $(ruby --version)"
            echo "PostgreSQL: $(psql --version | head -1)"
            echo "Port: $PGPORT"

            # Auto-setup database on shell entry
            db_setup
          '';
        };

      in
      {
        devShells.default = devSandbox;

        packages = {
          build-push = pkgs.writeShellApplication {
            name = "build-push";
            text = ''
              set -e
              REGISTRY="ghcr.io"
              REPO=$(git remote get-url origin 2>/dev/null | sed -E 's|.*github\.com[:/]||' | sed 's/\.git$//' | sed 's/$/-backend/' || echo "$USER/valoris-backend")
              TAG="''${REGISTRY}/''${REPO}:latest"
              echo "$GITHUB_TOKEN" | podman login "$REGISTRY" -u "josevictorferreira" --password-stdin
              podman build --platform=linux/amd64 --file Containerfile --tag "$TAG" .
              podman push "$TAG"
            '';
          };

          deploy = pkgs.writeShellApplication {
            name = "deploy";
            text = ''
              set -e
              REGISTRY="ghcr.io"
              REPO=$(git remote get-url origin 2>/dev/null | sed -E 's|.*github\.com[:/]||' | sed 's/\.git$//' | sed 's/$/-backend/' || echo "$USER/valoris-backend")
              TAG="''${REGISTRY}/''${REPO}:latest"
              echo "$GITHUB_TOKEN" | podman login "$REGISTRY" -u "josevictorferreira" --password-stdin
              podman build --platform=linux/amd64 --file Containerfile --tag "$TAG" .
              podman push "$TAG"
              kubectl --context=ze-homelab -n apps rollout restart deployment/valoris-backend deployment/valoris-worker
              kubectl --context=ze-homelab -n apps rollout status deployment/valoris-backend --timeout=300s
            '';
          };
        };
      }
    );
}
