repo_source := "git:github.com/rajp152k/pi-exts"
firefoxctl := "node integrations/firefox/bin/firefoxctl.mjs"

# List available recipes.
default:
    @just --list

# Install one named Pi integration bundle, for example: just install notify
install name:
    pi install "{{repo_source}}"
    python3 scripts/configure-package.py "{{repo_source}}" "{{name}}"

# Install every extension, skill, prompt, and theme in this package.
all:
    pi install "{{repo_source}}"
    python3 scripts/configure-package.py "{{repo_source}}"

# Update one installed integration bundle.
update name:
    pi update --extension "{{repo_source}}"
    python3 scripts/configure-package.py "{{repo_source}}" "{{name}}"

# Update every installed extension, skill, prompt, and theme in this package.
update-all:
    pi update --extension "{{repo_source}}"
    python3 scripts/configure-package.py "{{repo_source}}"

# Run CI-safe offline validation; excludes live browser, Pi, and tmux checks.
check:
    uv run --managed-python python scripts/check-capabilities.py
    uv run --managed-python python -m unittest discover -s skills/pi-task-dispatch/tests

# Start Firefox with Marionette and WebDriver BiDi enabled.
firefox-launch:
    integrations/firefox/scripts/launch-firefox-agent

# Verify Firefox, MCPorter, and the Firefox MCP connection.
firefox-doctor:
    {{firefoxctl}} doctor

# List live Firefox tabs through the persistent MCP connection.
firefox-tabs:
    {{firefoxctl}} tabs list

# Run the opt-in live Firefox smoke test against a local fixture page.
test-firefox:
    node integrations/firefox/test/smoke.mjs
