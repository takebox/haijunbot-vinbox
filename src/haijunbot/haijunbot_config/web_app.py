# -*- coding: utf-8 -*-
"""
FastAPI web application

Provides a web service for the configuration form
"""

import copy
import json
from pathlib import Path
from typing import Any, Dict

import yaml  # type: ignore[import-untyped]

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .schema_parser import SchemaParser


# Request model
class SaveConfigRequest(BaseModel):
    """Request model for saving configuration"""

    config: Dict[str, Any]


def create_app(schema_path: Path, output_path: Path) -> FastAPI:
    """Create the FastAPI application

    Args:
        schema_path: JSON Schema file path
        output_path: Output configuration file path

    Returns:
        FastAPI application instance
    """
    # Application instance-level state (closure variables), so that module-level global state is not polluted across multiple instances
    schema_parser = SchemaParser(schema_path)

    # Load the existing configuration file (if it exists)
    existing_config: Dict[str, Any] = {}
    if output_path.exists():
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                if output_path.suffix in (".yaml", ".yml"):
                    existing_config = yaml.safe_load(f) or {}
                else:
                    existing_config = json.load(f)
        except Exception:
            # If loading fails, use an empty configuration
            existing_config = {}

    # Create the FastAPI application
    app = FastAPI(
        title="HaijunBot Configuration Tool",
        description="Dynamic configuration form based on JSON Schema",
        version="1.0.0",
    )

    # Enable CORS
    # Note: allow_credentials=True and allow_origins=["*"] cannot be used together (browser specs forbid it,
    # otherwise a "Cannot use wildcard in Access-Control-Allow-Origin with credentials" error is raised).
    # For a local tool scenario, a wildcard origin is sufficient, and no credentials are carried.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        """Return the HTML page"""
        # TODO: implement the complete Zen-iOS Hybrid style frontend in task 4
        # Return a basic skeleton for now
        return get_html_template()

    @app.get("/api/schema")
    async def get_schema() -> Dict[str, Any]:
        """Get the Schema data

        Returns:
            The Schema object, containing properties, types, constraints, and other information
        """
        if schema_parser is None:
            raise HTTPException(status_code=500, detail="Schema parser not initialized")

        # Deep-copy the properties to avoid modifying the schema cached by the parser in place (repeated calls would nest-pollute _meta)
        properties = copy.deepcopy(schema_parser.get_properties())

        # Add extra metadata for each property
        for prop_name in properties:
            schema_default = schema_parser.get_default_value(prop_name)
            # If the existing configuration has a value for this property, use it to override the default
            if prop_name in existing_config:
                schema_default = existing_config[prop_name]

            properties[prop_name]["_meta"] = {
                "default": schema_default,
                "enum": schema_parser.get_enum(prop_name),
                "description": schema_parser.get_description_for_property(prop_name),
                "required": prop_name in schema_parser.get_required(),
            }

        return {
            "title": schema_parser.get_title(),
            "description": schema_parser.get_description(),
            "properties": properties,
            "required": schema_parser.get_required(),
        }

    @app.post("/api/save")
    async def save_config(request: SaveConfigRequest) -> Dict[str, Any]:
        """Save the configuration

        Args:
            request: Configuration data request

        Returns:
            The save result
        """

        # Remove null values from the configuration (recursively)
        def clean_null_values(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {
                    k: clean_null_values(v) for k, v in obj.items() if v is not None
                }
            elif isinstance(obj, list):
                return [clean_null_values(item) for item in obj if item is not None]
            return obj

        cleaned_config = clean_null_values(request.config)

        # Validate the configuration
        errors = schema_parser.validate_config(cleaned_config)
        if errors:
            return {
                "success": False,
                "errors": [
                    {"path": error.path, "message": error.message} for error in errors
                ],
            }

        # Save the configuration file
        try:
            # Ensure the output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if output_path.suffix in (".yaml", ".yml"):
                with open(output_path, "w", encoding="utf-8") as f:
                    yaml.dump(
                        cleaned_config,
                        f,
                        allow_unicode=True,
                        default_flow_style=False,
                        sort_keys=False,
                    )
            else:
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(cleaned_config, f, indent=2, ensure_ascii=False)

            return {
                "success": True,
                "message": f"Configuration saved to {output_path}",
                "path": str(output_path),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save configuration: {str(e)}")

    @app.get("/api/health")
    async def health_check() -> Dict[str, str]:
        """Health check"""
        return {"status": "ok"}

    @app.post("/api/shutdown")
    async def shutdown() -> Dict[str, str]:
        """Shut down the server"""
        import threading
        import os
        import signal

        def delayed_shutdown():
            """Delayed shutdown, ensuring the response is sent first"""
            import time

            time.sleep(0.5)
            os.kill(os.getpid(), signal.SIGTERM)

        threading.Thread(target=delayed_shutdown, daemon=True).start()
        return {"status": "shutting_down"}

    return app


def get_html_template() -> str:
    """Get the HTML template

    Returns:
        HTML string
    """
    return r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HaijunBot Configuration Tool</title>
    <script>
        function expandAll() {
            const sections = document.querySelectorAll('.form-section');
            
            // For each collapsed section, simulate a click on its collapse button to ensure consistent state
            for (let i = 0; i < sections.length; i++) {
                const toggleBtn = sections[i].querySelector('.collapse-toggle');
                if (toggleBtn && sections[i].classList.contains('collapsed')) {
                    // Simulate a click to ensure the toggleCollapse function is invoked
                    toggleBtn.click();
                }
            }
        }
        
        function collapseAll() {
            const sections = document.querySelectorAll('.form-section');
            
            // For each expanded section, simulate a click on its collapse button to ensure consistent state
            for (let i = 0; i < sections.length; i++) {
                const toggleBtn = sections[i].querySelector('.collapse-toggle');
                if (toggleBtn && !sections[i].classList.contains('collapsed')) {
                    // Simulate a click to ensure the toggleCollapse function is invoked
                    toggleBtn.click();
                }
            }
        }
    </script>
    <style>
        :root {
            --bg-primary: #F2F2F7;
            --bg-glass: rgba(255, 255, 255, 0.5);
            --bg-input: rgba(243, 244, 246, 0.5);
            --bg-input-focus: rgba(243, 244, 246, 0.7);
            --text-primary: #1C1C1E;
            --text-secondary: #6B7280;
            --text-label: #3C3C43;
            --border-inner: rgba(255, 255, 255, 0.6);
            --border-outer: rgba(0, 0, 0, 0.08);
            --button-primary: #1C1C1E;
            --button-primary-hover: #2C2C2E;
            --error: #DC2626;
            --error-bg: #FEE2E2;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.4;
            padding: 12px;
            min-height: 100vh;
        }

        .main-container {
            max-width: 1400px;
            margin: 0 auto;
        }

        #form-fields {
            display: grid;
            grid-template-columns: 1fr;
            gap: 10px;
        }

        /* Wide-screen multi-column layout */
        @media (min-width: 1024px) {
            #form-fields {
                grid-template-columns: repeat(2, 1fr);
            }

            /* Complex fields (containing nested objects or arrays) span the full row */
            .form-section:has(.nested-object),
            .form-section:has(.dict-container),
            .form-section:has(.array-item) {
                grid-column: 1 / -1;
            }
        }

        /* Ultra-wide screen three-column layout */
        @media (min-width: 1600px) {
            #form-fields {
                grid-template-columns: repeat(3, 1fr);
            }
        }

        .glass-card {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 20px;
            border: 1px solid var(--border-inner);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
            margin-bottom: 12px;
        }

        h1 {
            font-weight: 800;
            letter-spacing: -0.02em;
            font-size: 22px;
            margin-bottom: 4px;
            color: var(--text-primary);
        }

        .description {
            color: var(--text-secondary);
            font-size: 13px;
            line-height: 1.4;
            margin-bottom: 16px;
        }

        .loading, .error, .success {
            text-align: center;
            padding: 24px 16px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.95);
        }

        .loading {
            color: var(--text-secondary);
            font-size: 16px;
        }

        .error {
            background: var(--error-bg);
            color: var(--error);
            border: 1px solid rgba(220, 38, 38, 0.2);
        }

        .success {
            background: rgba(16, 185, 129, 0.1);
            color: #059669;
            border: 1px solid rgba(16, 185, 129, 0.2);
        }

        #form-container {
            display: none;
        }

        .form-section {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 12px;
            padding: 0;
            border: 1px solid var(--border-inner);
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
            /* With Grid layout, margin-bottom is no longer needed; spacing is controlled by gap */
        }
        
        .form-section-header {
            padding: 8px;
            border-bottom: 1px solid var(--border-inner);
            cursor: pointer;
            display: flex;
            align-items: center;
        }
        
        .collapse-toggle {
            background: none;
            border: none;
            font-size: 14px;
            cursor: pointer;
            color: var(--text-secondary);
            padding: 1px 4px;
            border-radius: 3px;
            margin-left: auto;
        }
        
        .form-section-header:hover {
            background: var(--bg-input-focus);
            border-radius: 12px 12px 0 0;
        }
        
        .form-section-content {
            padding: 8px;
            display: block;
        }
        
        .form-section.collapsed .form-section-content {
            display: none;
        }
        
        .form-section-header {
            cursor: pointer;
            user-select: none; /* Prevent accidental text selection */
        }
        
        .collapse-toggle {
            background: none;
            border: none;
            font-size: 14px;
            cursor: pointer;
            color: var(--text-secondary);
            padding: 1px 4px;
            border-radius: 3px;
        }
        
        .collapse-toggle:hover {
            background: var(--bg-input);
            color: var(--text-primary);
        }

        .form-group {
            margin-bottom: 6px;
        }

        .form-group:last-child {
            margin-bottom: 0;
        }

        label {
            display: block;
            font-weight: 700;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-label);
            margin-bottom: 4px;
        }

        .required-mark {
            color: var(--error);
            margin-left: 2px;
        }

        .field-description {
            display: inline-block;
            color: var(--text-secondary);
            font-size: 11px;
            margin-left: 6px;
            line-height: 1.3;
            vertical-align: middle;
        }

        .field-description.deprecated {
            color: #9CA3AF;
            font-style: italic;
            background: linear-gradient(135deg, rgba(156, 163, 175, 0.1), rgba(156, 163, 175, 0.05));
            padding: 4px 8px;
            border-radius: 4px;
            border-left: 3px solid #F59E0B;
        }

        .field-description.deprecated::before {
            content: "⚠️ ";
        }

        input[type="text"],
        input[type="number"],
        input[type="email"],
        input[type="url"],
        input[type="tel"],
        textarea,
        select {
            width: 100%;
            padding: 4px 8px;
            border: 1px solid var(--border-inner);
            border-radius: 6px;
            background: var(--bg-input);
            font-size: 13px;
            color: var(--text-primary);
            outline: none;
            box-shadow: var(--shadow-inset);
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", sans-serif;
        }

        input:focus,
        textarea:focus,
        select:focus {
            background: var(--bg-input-focus);
            border-color: rgba(0, 122, 255, 0.5);
            outline: none;
        }

        input::placeholder,
        textarea::placeholder {
            color: var(--text-secondary);
        }

        textarea {
            min-height: 60px;
            resize: vertical;
        }

        .checkbox-group,
        .radio-group {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .checkbox-item,
        .radio-item {
            display: flex;
            align-items: center;
            padding: 8px 12px;
            background: var(--bg-input);
            border: 1px solid var(--border-inner);
            border-radius: 8px;
            cursor: pointer;
        }

        .checkbox-item:hover,
        .radio-item:hover {
            background: var(--bg-input-focus);
        }

        .checkbox-item input,
        .radio-item input {
            width: 16px;
            height: 16px;
            margin-right: 8px;
            cursor: pointer;
            accent-color: var(--button-primary);
        }

        .switch-container {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 6px 12px;
            background: var(--bg-input);
            border: 1px solid var(--border-inner);
            border-radius: 8px;
        }

        .switch {
            position: relative;
            width: 40px;
            height: 24px;
            flex-shrink: 0;
        }

        .switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }

        .switch-slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #D1D1D6;
            border-radius: 12px;
        }

        .switch-slider:before {
            position: absolute;
            content: "";
            height: 20px;
            width: 20px;
            left: 2px;
            bottom: 2px;
            background-color: white;
            border-radius: 50%;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        }

        .switch input:checked + .switch-slider {
            background-color: #34C759;
        }

        .switch input:checked + .switch-slider:before {
            transform: translateX(16px);
        }

        .nested-object {
            background: rgba(243, 244, 246, 0.3);
            border-radius: 10px;
            padding: 12px;
            margin-top: 6px;
            border: 1px solid var(--border-inner);
        }

        .dict-container {
            background: var(--bg-input);
            border: 1px solid var(--border-inner);
            border-radius: 10px;
            padding: 10px;
        }

        .dict-item {
            background: var(--bg-glass);
            border: 1px solid var(--border-inner);
            border-radius: 8px;
            padding: 10px;
            margin-bottom: 8px;
        }

        .dict-item:last-child {
            margin-bottom: 0;
        }

        .dict-key-input {
            width: 100%;
            padding: 6px 10px;
            border: 1px solid var(--border-inner);
            border-radius: 6px;
            background: var(--bg-primary);
            font-size: 13px;
            color: var(--text-primary);
            outline: none;
            margin-bottom: 8px;
            box-shadow: var(--shadow-inset);
        }

        .dict-key-input:focus {
            background: rgba(243, 244, 246, 0.5);
            border-color: rgba(0, 122, 255, 0.5);
            outline: none;
        }

        .dict-controls {
            display: flex;
            gap: 8px;
            margin-top: 8px;
        }

        .dict-item-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
        }

        .dict-item-remove {
            margin-left: auto;
            flex-shrink: 0;
        }

        .array-item {
            background: var(--bg-input);
            border: 1px solid var(--border-inner);
            border-radius: 10px;
            padding: 10px;
            margin-bottom: 8px;
        }

        .array-item:last-child {
            margin-bottom: 0;
        }

        .array-controls {
            display: flex;
            gap: 8px;
            margin-top: 8px;
        }

        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 13px;
            cursor: pointer;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", sans-serif;
        }

        .btn-primary {
            background: var(--button-primary);
            color: white;
        }

        .btn-primary:hover {
            background: var(--button-primary-hover);
            transform: translateY(-1px);
        }

        .btn-secondary {
            background: white;
            color: var(--text-primary);
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }

        .btn-secondary:hover {
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
            transform: translateY(-1px);
        }

        .btn-danger {
            background: rgba(220, 38, 38, 0.1);
            color: var(--error);
            border: 1px solid rgba(220, 38, 38, 0.2);
        }

        .btn-danger:hover {
            background: rgba(220, 38, 38, 0.15);
        }

        .btn-sm {
            padding: 5px 12px;
            font-size: 12px;
            border-radius: 6px;
        }

        .btn-icon {
            width: 26px;
            height: 26px;
            padding: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 6px;
        }

        .form-actions {
            margin-top: 16px;
            display: flex;
            gap: 10px;
        }

        .field-error {
            color: var(--error);
            font-size: 11px;
            margin-top: 4px;
            display: none;
        }

        .has-error input,
        .has-error select,
        .has-error textarea {
            border-color: var(--error);
        }

        .has-error .field-error {
            display: block;
        }

        @media (max-width: 768px) {
            body {
                padding: 16px;
            }

            .glass-card {
                border-radius: 32px;
                padding: 32px 24px;
            }

            h1 {
                font-size: 28px;
            }

            .form-section {
                border-radius: 24px;
                padding: 24px 20px;
            }

            .form-actions {
                flex-direction: column;
            }

            .btn {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="main-container">
        <div class="glass-card">
            <h1 id="title">Loading...</h1>
            <p id="description" class="description"></p>
            
            <div id="loading" class="loading">
                <div style="margin-bottom: 16px;">
                    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#6B7280" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="3"></circle>
                        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                    </svg>
                </div>
                Loading configuration form...
            </div>
            
            <div id="error" class="error" style="display: none;"></div>
            <div id="success" class="success" style="display: none;"></div>
            
            <div id="form-container">
                <form id="config-form" novalidate>
                    <div style="display: flex; gap: 10px; margin-bottom: 16px;">
                        <button type="button" class="btn btn-secondary" onclick="expandAll()">Expand All</button>
                        <button type="button" class="btn btn-secondary" onclick="collapseAll()">Collapse All</button>
                    </div>
                    <div id="form-fields"></div>
                    <div class="form-actions">
                        <button type="submit" class="btn btn-primary">Save Configuration</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <script>
        let schemaData = null;
        let formData = {};
        let arrayCounters = {};
        let dictCounters = {};

        async function loadSchema() {
            try {
                const response = await fetch('/api/schema');
                if (!response.ok) throw new Error('Failed to load Schema');
                schemaData = await response.json();
                renderForm();
            } catch (error) {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('error').style.display = 'block';
                document.getElementById('error').textContent = error.message;
            }
        }

        function renderForm() {
            document.getElementById('loading').style.display = 'none';
            document.getElementById('form-container').style.display = 'block';

            document.getElementById('title').textContent = schemaData.title || 'Configuration';
            document.getElementById('description').textContent = schemaData.description || '';

            const fieldsContainer = document.getElementById('form-fields');
            fieldsContainer.innerHTML = '';
            
            // Use a DocumentFragment to add elements in batch and reduce reflow count
            const fragment = document.createDocumentFragment();

            for (const [name, prop] of Object.entries(schemaData.properties)) {
                const meta = prop._meta || {};
                const isRequired = schemaData.required.includes(name);

                const section = document.createElement('div');
                section.className = 'form-section';
                section.innerHTML = createFieldHTML(name, prop, meta, isRequired, []);
                fragment.appendChild(section);
            }
            
            fieldsContainer.appendChild(fragment);

            initializeFormValues();
        }

        function createFieldHTML(name, prop, meta, isRequired, path) {
            const type = prop.type;
            const fullPath = [...path, name];
            const fullPathStr = fullPath.join('.');
            const labelText = name + (isRequired ? '<span class="required-mark">*</span>' : '');
            
            // Create a collapsible form section, collapsed by default
            let html = '<div class="form-section collapsed">';
            html += '<div class="form-section-header">';
            html += '<span>' + labelText + '</span>';
            
            // If there is a description, add it after the label
            if (meta.description) {
                const isDeprecated = meta.description.includes('[deprecated');
                const descClass = isDeprecated ? 'field-description deprecated' : 'field-description';
                html += '<span class="' + descClass + '">' + escapeHtml(meta.description) + '</span>';
            }
            
            html += '<button type="button" class="collapse-toggle">▶</button>';
            html += '</div>';
            html += '<div class="form-section-content">';
            html += '<div class="form-group" data-path="' + fullPathStr + '">';

            if (prop.enum) {
                html += createSelectHTML(fullPathStr, prop.enum, meta.default);
            } else if (type === 'boolean') {
                html += createSwitchHTML(fullPathStr, meta.default);
            } else if (type === 'string' && prop.format === 'textarea') {
                html += createTextareaHTML(fullPathStr, prop, meta.default);
            } else if (type === 'number' || type === 'integer') {
                html += createNumberInputHTML(fullPathStr, prop, meta.default);
            } else if (type === 'array') {
                html += createArrayHTML(fullPathStr, prop, meta.default, fullPath);
            } else if (type === 'object') {
                // Determine whether it is a fixed-property object or a dictionary type
                if (prop.additionalProperties && !prop.properties) {
                    html += createDictHTML(fullPathStr, prop, meta.default, fullPath);
                } else {
                    html += createObjectHTML(fullPathStr, prop, meta.default, fullPath);
                }
            } else {
                html += createTextInputHTML(fullPathStr, prop, meta.default);
            }

            html += '<div class="field-error" id="error-' + fullPathStr + '"></div>';
            html += '</div>';
            html += '</div>';
            html += '</div>';

            return html;
        }

        function createTextInputHTML(path, prop, defaultValue) {
            const placeholder = prop.examples ? prop.examples[0] : '';
            const value = defaultValue !== undefined ? defaultValue : '';
            return '<input type="text" name="' + path + '" placeholder="' + escapeHtml(placeholder) + '" value="' + escapeHtml(String(value)) + '">';
        }

        function createNumberInputHTML(path, prop, defaultValue) {
            const min = prop.minimum !== undefined ? prop.minimum : '';
            const max = prop.maximum !== undefined ? prop.maximum : '';
            const value = defaultValue !== undefined ? defaultValue : '';
            return '<input type="number" name="' + path + '" min="' + min + '" max="' + max + '" value="' + value + '">';
        }

        function createTextareaHTML(path, prop, defaultValue) {
            const minLength = prop.minLength !== undefined ? prop.minLength : '';
            const maxLength = prop.maxLength !== undefined ? prop.maxLength : '';
            const value = defaultValue !== undefined ? defaultValue : '';
            return '<textarea name="' + path + '" minlength="' + minLength + '" maxlength="' + maxLength + '" placeholder="Enter content...">' + escapeHtml(String(value)) + '</textarea>';
        }

        function createSelectHTML(path, enumValues, defaultValue) {
            let html = '<select name="' + path + '">';
            if (defaultValue === undefined) {
                html += '<option value="">Please select...</option>';
            }
            enumValues.forEach(function(value) {
                const selected = value === defaultValue ? ' selected' : '';
                html += '<option value="' + escapeHtml(String(value)) + '"' + selected + '>' + escapeHtml(String(value)) + '</option>';
            });
            html += '</select>';
            return html;
        }

        function createSwitchHTML(path, defaultValue) {
            const checked = defaultValue === true ? 'checked' : '';
            return '<div class="switch-container">\n                <span>' + (defaultValue === true ? 'Enabled' : 'Disabled') + '</span>\n                <label class="switch">\n                    <input type="checkbox" name="' + path + '" value="true" ' + checked + '>\n                    <span class="switch-slider"></span>\n                </label>\n            </div>';
        }

        function createArrayHTML(path, prop, defaultValue, parentPath) {
            // path is already the full path string
            // parentPath is no longer used; the parameter is kept for compatibility
            const fullPathStr = path;
            
            if (!arrayCounters[fullPathStr]) {
                arrayCounters[fullPathStr] = 0;
            }

            // Create the array container, without its own collapse functionality
            let html = '<div class="array-container" data-path="' + fullPathStr + '">';
            html += '<div id="array-items-' + fullPathStr + '"></div>';
            html += '<div class="array-controls">';
            html += '<button type="button" class="btn btn-secondary btn-sm" onclick="addArrayItem(\'' + fullPathStr + '\')">+ Add Item</button>';
            html += '</div></div>';
            html += '</div>';
            html += '</div>';

            setTimeout(function() {
                const itemsContainer = document.getElementById('array-items-' + fullPathStr);
                if (itemsContainer) {
                    itemsContainer.dataset.schema = JSON.stringify(prop.items || {});
                    
                    // Initialize existing array items
                    if (Array.isArray(defaultValue) && defaultValue.length > 0) {
                        const schema = prop.items || {};
                        defaultValue.forEach(function(itemValue) {
                            const index = arrayCounters[fullPathStr]++;
                            const itemPath = fullPathStr + '[' + index + ']';

                            const itemDiv = document.createElement('div');
                            itemDiv.className = 'array-item';
                            itemDiv.dataset.index = index;

                            let fieldHTML = '';
                            if (schema.type === 'object') {
                                for (const propName in schema.properties || {}) {
                                    const propSchema = schema.properties[propName];
                                    // Create metadata for object-type array items, including default values
                                    const propMeta = {
                                        default: itemValue && itemValue[propName] !== undefined ? itemValue[propName] : propSchema.default,
                                        description: propSchema.description,
                                        enum: propSchema.enum
                                    };
                                    const propRequired = (schema.required || []).includes(propName);
                                    fieldHTML += createFieldHTML(propName, propSchema, propMeta, propRequired, [itemPath]);
                                }
                            } else {
                                // Create an input directly for simple-type array items, without a label
                                if (schema.enum) {
                                    fieldHTML += createSelectHTML(itemPath, schema.enum, itemValue !== undefined ? itemValue : schema.default);
                                } else if (schema.type === 'boolean') {
                                    fieldHTML += createSwitchHTML(itemPath, itemValue !== undefined ? itemValue : schema.default);
                                } else if (schema.type === 'string' && schema.format === 'textarea') {
                                    fieldHTML += createTextareaHTML(itemPath, schema, itemValue !== undefined ? itemValue : schema.default);
                                } else if (schema.type === 'number' || schema.type === 'integer') {
                                    fieldHTML += createNumberInputHTML(itemPath, schema, itemValue !== undefined ? itemValue : schema.default);
                                } else {
                                    fieldHTML += createTextInputHTML(itemPath, schema, itemValue !== undefined ? itemValue : schema.default);
                                }
                            }

                            itemDiv.innerHTML = fieldHTML;
                            itemDiv.innerHTML += '<button type="button" class="btn btn-danger btn-sm btn-icon" onclick="removeArrayItem(\'' + fullPathStr + '\', ' + index + ')" style="margin-top: 16px;">×</button>';

                            itemsContainer.appendChild(itemDiv);
                        });
                    }
                }
            }, 0);

            return html;
        }

        function addArrayItem(path) {
            const container = document.getElementById('array-items-' + path);
            if (!container) return;

            const schema = JSON.parse(container.dataset.schema || '{}');
            const index = arrayCounters[path]++;
            const itemPath = path + '[' + index + ']';

            const itemDiv = document.createElement('div');
            itemDiv.className = 'array-item';
            itemDiv.dataset.index = index;

            let fieldHTML = '';
            if (schema.type === 'object') {
                for (const propName in schema.properties || {}) {
                    const propSchema = schema.properties[propName];
                    const propMeta = propSchema._meta || {};
                    const propRequired = (schema.required || []).includes(propName);
                    fieldHTML += createFieldHTML(propName, propSchema, propMeta, propRequired, [itemPath]);
                }
            } else {
                // Create an input directly for simple-type array items, without a label
                if (schema.enum) {
                    fieldHTML += createSelectHTML(itemPath, schema.enum, schema._meta?.default);
                } else if (schema.type === 'boolean') {
                    fieldHTML += createSwitchHTML(itemPath, schema._meta?.default);
                } else if (schema.type === 'string' && schema.format === 'textarea') {
                    fieldHTML += createTextareaHTML(itemPath, schema, schema._meta?.default);
                } else if (schema.type === 'number' || schema.type === 'integer') {
                    fieldHTML += createNumberInputHTML(itemPath, schema, schema._meta?.default);
                } else {
                    fieldHTML += createTextInputHTML(itemPath, schema, schema._meta?.default);
                }
            }

            itemDiv.innerHTML = fieldHTML;
            itemDiv.innerHTML += '<button type="button" class="btn btn-danger btn-sm btn-icon" onclick="removeArrayItem(\'' + path + '\', ' + index + ')" style="margin-top: 16px;">×</button>';

            container.appendChild(itemDiv);
        }

        function removeArrayItem(path, index) {
            const container = document.getElementById('array-items-' + path);
            if (!container) return;

            const item = container.querySelector('[data-index="' + index + '"]');
            if (item) {
                item.remove();
            }
        }

        function createObjectHTML(path, prop, defaultValue, parentPath) {
            // path is already the full path string
            // parentPath is the array containing the full path, used for passing to child fields
            const fullPathStr = path;
            
            // Create the object container, without its own collapse functionality
            let html = '<div class="nested-object" data-path="' + fullPathStr + '">';
            
            for (const propName in prop.properties || {}) {
                const propSchema = prop.properties[propName];
                const propMeta = propSchema._meta || {};
                const propRequired = (prop.required || []).includes(propName);
                html += createFieldHTML(propName, propSchema, propMeta, propRequired, parentPath);
            }
            
            html += '</div>';
            html += '</div>';
            html += '</div>';
            return html;
        }

        function createDictHTML(path, prop, defaultValue, parentPath) {
            // path is already the full path string (e.g. "llms[glm].llm_config")
            // parentPath is no longer used; the parameter is kept for compatibility
            const fullPathStr = path;
            
            if (!dictCounters[fullPathStr]) {
                dictCounters[fullPathStr] = Object.keys(defaultValue || {}).length;
            }
            
            // Create the dictionary container, without its own collapse functionality
            let html = '<div class="dict-container" data-path="' + fullPathStr + '">';
            html += '<div id="dict-items-' + fullPathStr + '"></div>';
            html += '<div class="dict-controls">';
            html += '<button type="button" class="btn btn-secondary btn-sm" onclick="addDictItem(\'' + fullPathStr + '\')">+ Add Entry</button>';
            html += '</div></div>';
            html += '</div>';
            html += '</div>';
            
            setTimeout(function() {
                const itemsContainer = document.getElementById('dict-items-' + fullPathStr);
                if (itemsContainer) {
                    itemsContainer.dataset.schema = JSON.stringify(prop.additionalProperties || {});
                    itemsContainer.dataset.defaultValue = JSON.stringify(defaultValue || {});
                    // Initialize existing entries
                    for (const key in defaultValue || {}) {
                        addDictItem(fullPathStr, key, defaultValue[key]);
                    }
                }
            }, 0);
            
            return html;
        }

        function addDictItem(path, existingKey, existingValue) {
            const container = document.getElementById('dict-items-' + path);
            if (!container) return;

            const schema = JSON.parse(container.dataset.schema || '{}');
            const itemId = 'dict-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);

            const itemDiv = document.createElement('div');
            itemDiv.className = 'dict-item';
            itemDiv.dataset.id = itemId;

            const key = existingKey || '';
            let fieldHTML = '';

            if (existingKey) {
                // Edit an existing entry; create the key-name display and value fields
                fieldHTML = '<div class="dict-item-header">';
                fieldHTML += '<label>Key: ' + escapeHtml(String(existingKey)) + '</label>';
                fieldHTML += '<button type="button" class="btn btn-danger btn-sm btn-icon dict-item-remove" onclick="removeDictItem(\'' + path + '\', \'' + itemId + '\')">×</button>';
                fieldHTML += '</div>';

                // Create different fields based on the value type
                const valuePath = [path + '[' + existingKey + ']'];
                if (schema.type === 'object' && schema.properties) {
                    // Object type: iterate over all properties
                    for (const propName in schema.properties || {}) {
                        const propSchema = schema.properties[propName];
                        const propDefaultValue = (existingValue || {})[propName];
                        const propMeta = {
                            default: propDefaultValue !== undefined ? propDefaultValue : propSchema.default,
                            description: propSchema.description,
                            enum: propSchema.enum
                        };
                        const propRequired = (schema.required || []).includes(propName);
                        fieldHTML += createFieldHTML(propName, propSchema, propMeta, propRequired, valuePath);
                    }
                } else {
                    // Non-object type: use the path directly as the field name, without an extra suffix
                    const fieldPath = path + '[' + existingKey + ']';
                    const defaultVal = existingValue !== undefined ? existingValue : (schema.default || '');
                    if (schema.type === 'boolean') {
                        fieldHTML += createSwitchHTML(fieldPath, defaultVal);
                    } else if (schema.type === 'number' || schema.type === 'integer') {
                        fieldHTML += createNumberInputHTML(fieldPath, schema, defaultVal);
                    } else {
                        fieldHTML += createTextInputHTML(fieldPath, schema, defaultVal);
                    }
                }
            } else {
                // Add a new entry; create the key-name input and value fields
                // Use the special name attribute format: path[__key__] identifies this as the key-name input
                // Add an oninput event to update the name attributes of related fields as soon as the user types a key name
                fieldHTML = '<input type="text" class="dict-key-input" name="' + path + '[__key__]' + '" placeholder="Enter key name..." value="" oninput="updateDictKey(\'' + path + '\', \'' + itemId + '\', this.value)">';

                // Create different fields based on the value type
                // Use the temporary key name __temp__; it will be replaced according to the actual key-name input value when collecting data
                if (schema.type === 'object' && schema.properties) {
                    // Object type: iterate over all properties
                    const valuePath = [path + '[__temp__]'];
                    for (const propName in schema.properties || {}) {
                        const propSchema = schema.properties[propName];
                        const propMeta = {
                            default: propSchema.default,
                            description: propSchema.description,
                            enum: propSchema.enum
                        };
                        const propRequired = (schema.required || []).includes(propName);
                        fieldHTML += createFieldHTML(propName, propSchema, propMeta, propRequired, valuePath);
                    }
                } else {
                    // Simple type: create the input directly
                    const fieldPath = path + '[__temp__]';
                    if (schema.type === 'boolean') {
                        fieldHTML += createSwitchHTML(fieldPath, schema.default);
                    } else if (schema.type === 'number' || schema.type === 'integer') {
                        fieldHTML += createNumberInputHTML(fieldPath, schema, schema.default);
                    } else {
                        fieldHTML += createTextInputHTML(fieldPath, schema, schema.default || '');
                    }
                }
                fieldHTML += '<button type="button" class="btn btn-danger btn-sm btn-icon dict-item-remove" onclick="removeDictItem(\'' + path + '\', \'' + itemId + '\')" style="margin-top: 12px;">×</button>';
            }

            itemDiv.innerHTML = fieldHTML;
            container.appendChild(itemDiv);

            if (!existingKey) {
                // Auto-focus the key-name input for new entries
                const keyInput = itemDiv.querySelector('.dict-key-input');
                if (keyInput) {
                    keyInput.focus();
                }
            }
        }

        function updateDictKey(path, itemId, newKey) {
            const container = document.getElementById('dict-items-' + path);
            if (!container) return;

            const item = container.querySelector('[data-id="' + itemId + '"]');
            if (!item) return;

            // Get the currently stored key name; default to __temp__ if none
            const currentKey = item.dataset.currentKey || '__temp__';
            
            // Update the name attributes of all value fields
            const valueFields = item.querySelectorAll('[name]');
            if (newKey) {
                valueFields.forEach(function(valueField) {
                    const oldName = valueField.getAttribute('name');
                    // Skip the key-name input itself
                    if (oldName === path + '[__key__]') {
                        return;
                    }
                    // Match patterns: path[currentKey], path[currentKey].subfield, or path[currentKey][subkey]
                    // Match using the currently stored key name
                    const keyPattern = new RegExp('^' + escapeRegExp(path) + '\\[' + escapeRegExp(currentKey) + '\\](.*)$');
                    const match = oldName.match(keyPattern);
                    if (match) {
                        const suffix = match[1];
                        valueField.setAttribute('name', path + '[' + newKey + ']' + suffix);
                    }
                });
                // Update the stored current key name
                item.dataset.currentKey = newKey;
            }
        }

        function removeDictItem(path, itemId) {
            const container = document.getElementById('dict-items-' + path);
            if (!container) return;

            const item = container.querySelector('[data-id="' + itemId + '"]');
            if (item) {
                item.remove();
            }
        }

        function initializeFormValues() {
            document.querySelectorAll('.switch input').forEach(function(switchEl) {
                updateSwitchText(switchEl);
                switchEl.addEventListener('change', function(e) { updateSwitchText(e.target); });
            });
        }

        function updateSwitchText(checkbox) {
            const container = checkbox.closest('.switch-container');
            const textSpan = container.querySelector('span');
            if (textSpan) {
                textSpan.textContent = checkbox.checked ? 'Enabled' : 'Disabled';
            }
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function toggleCollapse(element) {
            const section = element.closest('.form-section');
            if (section) {
                // Get the collapse button
                const toggleBtn = element.classList.contains('collapse-toggle') ? element : section.querySelector('.collapse-toggle');
                
                // Check whether the current state is collapsed
                const isCurrentlyCollapsed = section.classList.contains('collapsed');
                
                if (isCurrentlyCollapsed) {
                    // Currently collapsed; expand it
                    section.classList.remove('collapsed');
                    
                    // Ensure the class is removed before setting the button text
                    setTimeout(() => {
                        if (toggleBtn) {
                            toggleBtn.textContent = '▼';
                        }
                    }, 0);
                } else {
                    // Currently expanded; collapse it
                    section.classList.add('collapsed');
                    
                    // Ensure the class is added before setting the button text
                    setTimeout(() => {
                        if (toggleBtn) {
                            toggleBtn.textContent = '▶';
                        }
                    }, 0);
                }
            }
        }

        function escapeRegExp(str) {
            return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        }

        function clearErrors() {
            document.querySelectorAll('.has-error').forEach(function(el) { el.classList.remove('has-error'); });
            document.querySelectorAll('.field-error').forEach(function(el) { el.textContent = ''; });
        }

        function showError(path, message) {
            const fieldGroup = document.querySelector('[data-path="' + path + '"]');
            if (fieldGroup) {
                fieldGroup.classList.add('has-error');
                const errorDiv = document.getElementById('error-' + path);
                if (errorDiv) {
                    errorDiv.textContent = message;
                }
            }
        }

        async function handleSubmit(event) {
            event.preventDefault();
            
            clearErrors();
            const config = {};
            
            const formData = new FormData(event.target);
            
            for (const name in schemaData.properties) {
                const prop = schemaData.properties[name];
                const value = collectFieldValue(name, prop, formData);
                if (value !== undefined) {
                    config[name] = value;
                }
            }
            
            for (let i = 0; i < schemaData.required.length; i++) {
                const required = schemaData.required[i];
                if (config[required] === undefined || config[required] === '' || config[required] === null) {
                    showError(required, 'This field is required');
                    return;
                }
            }

            try {
                const response = await fetch('/api/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ config: config })
                });

                const result = await response.json();

                if (result.success) {
                    // Show a success notification
                    alert('✅ ' + result.message + '\n\nThe page will close now...');
                    
                    // Call the shutdown endpoint to stop the server
                    fetch('/api/shutdown', { method: 'POST' }).catch(() => {});
                    
                    // Close the page
                    setTimeout(function() {
                        window.close();
                        // If window.close() does not work (window not opened by script), show a hint
                        document.body.innerHTML = '<div style="display:flex;justify-content:center;align-items:center;height:100vh;font-size:24px;color:#059669;">✅ Configuration saved, please close this page manually</div>';
                    }, 500);
                } else {
                    for (let i = 0; i < result.errors.length; i++) {
                        const err = result.errors[i];
                        showError(err.path, err.message);
                    }
                }
            } catch (error) {
                document.getElementById('error').style.display = 'block';
                document.getElementById('error').textContent = 'Request failed: ' + error.message;
            }
        }

        // Helper function: parse a path string into a nested object and set the value
        function setNestedValue(obj, path, value) {
            // Parse the path, supporting .field and [key] formats
            const parts = [];
            let remaining = path;
            while (remaining) {
                if (remaining.startsWith('.')) {
                    // Handle the .field format
                    remaining = remaining.substring(1);
                    const dotMatch = remaining.match(/^([^.\[]+)/);
                    if (dotMatch) {
                        parts.push(dotMatch[1]);
                        remaining = remaining.substring(dotMatch[1].length);
                    }
                } else if (remaining.startsWith('[')) {
                    // Handle the [key] format
                    const bracketMatch = remaining.match(/^\[([^\]]+)\]/);
                    if (bracketMatch) {
                        parts.push(bracketMatch[1]);
                        remaining = remaining.substring(bracketMatch[0].length);
                    } else {
                        break;
                    }
                } else {
                    break;
                }
            }
            
            // Set the nested value
            let current = obj;
            for (let i = 0; i < parts.length - 1; i++) {
                if (!current[parts[i]]) {
                    current[parts[i]] = {};
                }
                current = current[parts[i]];
            }
            if (parts.length > 0) {
                current[parts[parts.length - 1]] = value;
            }
        }

        // Helper function: recursively process the __key__ and __temp__ keys in nested objects
        function processNestedDictKeys(obj) {
            if (typeof obj !== 'object' || obj === null) {
                return obj;
            }
            
            if (Array.isArray(obj)) {
                return obj.map(item => processNestedDictKeys(item));
            }
            
            const result = {};
            let tempValue = null;
            let actualKey = null;
            
            // First pass: collect the values of __key__ and __temp__
            for (const key in obj) {
                if (key === '__key__') {
                    actualKey = obj[key];
                } else if (key === '__temp__') {
                    tempValue = processNestedDictKeys(obj[key]);
                } else {
                    // Recursively process the values of other keys
                    result[key] = processNestedDictKeys(obj[key]);
                }
            }
            
            // If both __key__ and __temp__ exist, replace with the actual key name
            if (actualKey && tempValue !== null) {
                result[actualKey] = tempValue;
            } else if (tempValue !== null && !actualKey) {
                // If there is __temp__ but no __key__, keep the value of __temp__ but log a warning
                // This should not happen, but handle it for safety
                result['__temp__'] = tempValue;
            }
            
            return result;
        }

        function collectFieldValue(name, prop, formData) {
            const type = prop.type;

            // First check whether it is a dictionary type (object with additionalProperties but no properties)
            if (type === 'object' && prop.additionalProperties && !prop.properties) {
                const dict = {};
                const tempData = {};  // Store the data of the temporary key __temp__
                let actualKeyName = null;  // Store the actual key name typed by the user
                const entries = formData.entries();

                for (const [key, value] of entries) {
                    const match = key.match(new RegExp('^' + escapeRegExp(name) + '\\[([^\\]]+)\\](.*)$'));
                    if (match) {
                        const dictKey = match[1];
                        const subPath = match[2];

                        // Collect the value of the __key__ key (the actual key name typed by the user)
                        if (dictKey === '__key__') {
                            if (value && value.trim() !== '') {
                                actualKeyName = value.trim();
                            }
                            continue;
                        }

                        // If it is the __temp__ key, store it in tempData first
                        if (dictKey === '__temp__') {
                            if (!tempData.__temp__) {
                                tempData.__temp__ = subPath ? {} : value;
                            }
                            if (subPath) {
                                setNestedValue(tempData.__temp__, subPath, value);
                            } else {
                                tempData.__temp__ = value;
                            }
                            continue;
                        }

                        // A normal dictionary key
                        if (!dict[dictKey]) {
                            dict[dictKey] = subPath ? {} : value;
                        }

                        if (subPath) {
                            // Use the helper function to handle deeply nested paths
                            setNestedValue(dict[dictKey], subPath, value);
                        } else {
                            dict[dictKey] = value;
                        }
                    }
                }

                // Process the data of the temporary key __temp__
                // Use the actual key name collected during the first pass
                if (tempData.__temp__ !== undefined && actualKeyName) {
                    if (!dict[actualKeyName]) {
                        dict[actualKeyName] = tempData.__temp__;
                    } else {
                        // If the key already exists, merge the data
                        if (typeof dict[actualKeyName] === 'object' && typeof tempData.__temp__ === 'object') {
                            Object.assign(dict[actualKeyName], tempData.__temp__);
                        } else {
                            dict[actualKeyName] = tempData.__temp__;
                        }
                    }
                }

                // Type conversion
                const valueSchema = prop.additionalProperties || {};
                if (valueSchema.type === 'number' || valueSchema.type === 'integer') {
                    for (const key in dict) {
                        dict[key] = valueSchema.type === 'integer' ? parseInt(dict[key]) : parseFloat(dict[key]);
                    }
                } else if (valueSchema.type === 'boolean') {
                    for (const key in dict) {
                        dict[key] = dict[key] === 'true';
                    }
                }

                // Recursively process the __key__ and __temp__ keys in nested objects
                const processedDict = processNestedDictKeys(dict);
                return Object.keys(processedDict).length > 0 ? processedDict : prop.default || {};
            }
            
            if (type === 'array') {
                const values = [];
                const entries = formData.entries();
                let index = 0;
                
                for (const [key, value] of entries) {
                    if (key.startsWith(name + '[')) {
                        const match = key.match(new RegExp('^' + escapeRegExp(name) + '\\[(\\d+)\\](.*)$'));
                        if (match) {
                            const idx = parseInt(match[1]);
                            const subPath = match[2];
                            
                            while (values.length <= idx) {
                                values.push(subPath ? {} : null);
                            }
                            
                            if (subPath) {
                                if (subPath.startsWith('.')) {
                                    const subField = subPath.substring(1);
                                    if (!values[idx]) values[idx] = {};
                                    values[idx][subField] = value;
                                } else {
                                    values[idx][subPath] = value;
                                }
                            } else {
                                values[idx] = value;
                            }
                        }
                    }
                }
                
                if (values.length === 0) {
                    return prop.default || [];
                }
                
                const itemSchema = prop.items || {};
                if (itemSchema.type === 'number' || itemSchema.type === 'integer') {
                    return values.map(v => v ? (itemSchema.type === 'integer' ? parseInt(v) : parseFloat(v)) : v).filter(v => v !== null && v !== '');
                } else if (itemSchema.type === 'boolean') {
                    return values.map(v => v === 'true').filter(v => v !== null && v !== '');
                }
                
                return values.filter(v => v !== null && v !== '');
            }
            
            if (type === 'object') {
                const obj = {};
                const entries = formData.entries();
                const prefix = name + '.';
                
                for (const [key, value] of entries) {
                    if (key.startsWith(prefix)) {
                        const subField = key.substring(prefix.length);
                        if (prop.properties && prop.properties[subField]) {
                            const subType = prop.properties[subField].type;
                            if (subType === 'boolean') {
                                obj[subField] = value === 'true';
                            } else if (subType === 'number' || subType === 'integer') {
                                obj[subField] = subType === 'integer' ? parseInt(value) : parseFloat(value);
                            } else {
                                obj[subField] = value;
                            }
                        } else {
                            obj[subField] = value;
                        }
                    }
                }
                
                return Object.keys(obj).length > 0 ? obj : prop.default || {};
            }
            
            const value = formData.get(name);

            if (value === null || value === '') {
                if (type === 'boolean') {
                    return false;  // Return false when the checkbox is unchecked, instead of the default value
                }
                return prop.default;
            }

            if (type === 'boolean') {
                return value === 'true';
            } else if (type === 'number' || type === 'integer') {
                return type === 'integer' ? parseInt(value) : parseFloat(value);
            } else {
                return value;
            }
        }

        // Use event delegation to handle collapse operations
        document.getElementById('form-fields').addEventListener('click', function(e) {
            if (e.target.classList.contains('form-section-header')) {
                // If the collapse button was clicked, do not trigger the header collapse
                if (!e.target.classList.contains('collapse-toggle')) {
                    toggleCollapse(e.target);
                }
            } else if (e.target.classList.contains('collapse-toggle')) {
                e.stopPropagation();
                toggleCollapse(e.target.closest('.form-section'));
            }
        });
        
        document.getElementById('config-form').addEventListener('submit', handleSubmit);
        loadSchema();
    </script>
</body>
</html>
"""
