"""
Handlebars-inspired template engine for WifiCities themes.

Supports:
  {{variable}}          — HTML-escaped variable
  {{{variable}}}        — raw (unescaped) variable
  {{> partial_name}}    — include a partial
  {{> plugin:name}}     — include a plugin partial
  {{#each list}}...{{/each}}  — loop over a list
  {{#if cond}}...{{/if}}      — conditional
  {{#if cond}}...{{else}}...{{/if}} — conditional with else
"""
import re
import html
from pathlib import Path
from typing import Any


def render(template: str, variables: dict[str, Any],
           partials_dir: Path | None = None,
           plugin_partials: dict[str, str] | None = None) -> str:
    """Render a template string with the given variables and partials."""
    result = template

    # Resolve partials first (they may contain variables/loops/conditionals)
    result = _resolve_partials(result, partials_dir, plugin_partials)

    # Resolve conditionals
    result = _resolve_conditionals(result, variables)

    # Resolve loops
    result = _resolve_loops(result, variables)

    # Resolve raw variables {{{var}}} (unescaped)
    result = _resolve_raw_variables(result, variables)

    # Resolve escaped variables {{var}}
    result = _resolve_variables(result, variables)

    return result


def _resolve_partials(template: str, partials_dir: Path | None,
                      plugin_partials: dict[str, str] | None) -> str:
    """Resolve {{> partial_name}} includes."""
    max_depth = 10  # prevent infinite recursion
    for _ in range(max_depth):
        found = False

        # Plugin partials: {{> plugin:name}}
        def replace_plugin_partial(match):
            nonlocal found
            name = match.group(1).strip()
            if plugin_partials and name in plugin_partials:
                found = True
                return plugin_partials[name]
            return match.group(0)

        template = re.sub(r'\{\{>\s*plugin:(\S+?)\s*\}\}',
                          replace_plugin_partial, template)

        # Theme partials: {{> name}}
        def replace_partial(match):
            nonlocal found
            name = match.group(1).strip()
            if partials_dir:
                partial_path = partials_dir / f"{name}.html"
                if partial_path.exists():
                    found = True
                    return partial_path.read_text(encoding="utf-8")
            return match.group(0)

        template = re.sub(r'\{\{>\s*([a-zA-Z0-9_-]+)\s*\}\}',
                          replace_partial, template)

        if not found:
            break

    return template


def _resolve_conditionals(template: str, variables: dict[str, Any]) -> str:
    """Resolve {{#if cond}}...{{else}}...{{/if}} blocks."""
    # Handle if/else
    pattern = re.compile(
        r'\{\{#if\s+(\w+)\s*\}\}(.*?)(?:\{\{else\}\}(.*?))?\{\{/if\}\}',
        re.DOTALL
    )

    def replace_if(match):
        var_name = match.group(1)
        true_block = match.group(2)
        false_block = match.group(3) or ""

        value = variables.get(var_name)
        is_truthy = bool(value) and value != [] and value != 0

        return true_block if is_truthy else false_block

    # Apply repeatedly (nested conditionals)
    for _ in range(10):
        new_template = pattern.sub(replace_if, template)
        if new_template == template:
            break
        template = new_template

    return template


def _resolve_loops(template: str, variables: dict[str, Any]) -> str:
    """Resolve {{#each list}}...{{/each}} blocks."""
    pattern = re.compile(
        r'\{\{#each\s+(\w+)\s*\}\}(.*?)\{\{/each\}\}',
        re.DOTALL
    )

    def replace_each(match):
        var_name = match.group(1)
        body = match.group(2)
        items = variables.get(var_name, [])

        if not isinstance(items, list):
            return ""

        result = []
        for item in items:
            item_str = body
            if isinstance(item, dict):
                # Replace item properties
                for key, val in item.items():
                    item_str = item_str.replace("{{" + key + "}}", str(val))
                    item_str = item_str.replace("{{{" + key + "}}}", str(val))
            else:
                # Simple value — replace {{.}}
                item_str = item_str.replace("{{.}}", str(item))
                item_str = item_str.replace("{{{.}}}", str(item))
            result.append(item_str)

        return "".join(result)

    for _ in range(10):
        new_template = pattern.sub(replace_each, template)
        if new_template == template:
            break
        template = new_template

    return template


def _resolve_raw_variables(template: str, variables: dict[str, Any]) -> str:
    """Resolve {{{variable}}} — unescaped."""
    def replace_raw(match):
        var_name = match.group(1).strip()
        value = variables.get(var_name, "")
        return str(value)

    return re.sub(r'\{\{\{(\w+)\}\}\}', replace_raw, template)


def _resolve_variables(template: str, variables: dict[str, Any]) -> str:
    """Resolve {{variable}} — HTML-escaped."""
    def replace_var(match):
        var_name = match.group(1).strip()
        value = variables.get(var_name, "")
        return html.escape(str(value))

    return re.sub(r'\{\{(\w+)\}\}', replace_var, template)
