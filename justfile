repo_source := "git:github.com/rajp152k/pi-exts"

# List available recipes.
default:
    @just --list

# Install one extension by its non-namespaced name, for example: just install notify
install name:
    test -f "extensions/rp152kpi:{{name}}/index.ts"
    pi install "{{repo_source}}"
    python3 scripts/configure-package.py "{{repo_source}}" "{{name}}"

# Install every extension in this package.
all:
    pi install "{{repo_source}}"
    python3 scripts/configure-package.py "{{repo_source}}"

# Update one installed extension by its non-namespaced name.
update name:
    test -f "extensions/rp152kpi:{{name}}/index.ts"
    pi update --extension "{{repo_source}}"
    python3 scripts/configure-package.py "{{repo_source}}" "{{name}}"

# Update every installed extension in this package.
update-all:
    pi update --extension "{{repo_source}}"
    python3 scripts/configure-package.py "{{repo_source}}"
