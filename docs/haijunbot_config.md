# 📋 haijunbot_config Usage Guide

`haijunbot_config` is a tool that dynamically generates a configuration web page based on a JSON Schema, providing a friendly visual interface for managing and editing configuration files.

## ✨ Core Features

- 🎨 **Zen-iOS Hybrid style**: exquisite frosted-glass effects, double-layer physical strokes, haptic feedback
- 📝 **Dynamic form generation**: automatically generates forms based on the JSON Schema, supporting multiple field types
- ✅ **Real-time validation**: automatically validates whether the configuration conforms to the Schema specification on form submission
- 🚀 **Simple and easy to use**: start the web service with a single command, no extra configuration required
- 📄 **Multi-format support**: automatically supports JSON and YAML output based on the file extension

---

## 🚀 Quick Start

### Basic Usage

```bash
# Start the web configuration UI (using the default schema and output path)
haijunbot-config web

# Specify the schema and output file (JSON format)
haijunbot-config web --schema schema.json --output config.json

# Specify the schema and output file (YAML format)
haijunbot-config web --schema schema.json --output config.yaml

# Specify the port
haijunbot-config web --port 3000

# Disable automatically opening the browser
haijunbot-config web --no-browser
```

### Example Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Application Configuration",
  "description": "Basic configuration for the application",
  "type": "object",
  "required": ["name", "port"],
  "properties": {
    "name": {
      "type": "string",
      "description": "Application name",
      "minLength": 1,
      "default": "my-app"
    },
    "port": {
      "type": "integer",
      "description": "Service port",
      "minimum": 1,
      "maximum": 65535,
      "default": 8080
    },
    "enabled": {
      "type": "boolean",
      "description": "Whether enabled",
      "default": true
    },
    "mode": {
      "type": "string",
      "enum": ["development", "production", "test"],
      "description": "Run mode",
      "default": "development"
    }
  }
}
```

---

## 📖 Command-Line Interface

### The `web` Command

Starts the web configuration UI and generates a configuration form based on the specified Schema file.

```bash
haijunbot-config web [OPTIONS]
```

#### Options

| Option         | Short | Default                          | Description                               |
| -------------- | ----- | -------------------------------- | ----------------------------------------- |
| `--schema`     | `-s`  | `haijunbot_data/config_schema.json` | JSON Schema file path                     |
| `--output`     | `-o`  | `~/.haijunbot/config.yaml`          | Output configuration file path            |
| `--port`       | `-p`  | `8080`                           | Web service listening port                |
| `--no-browser` | `/nb` | `False`                          | Disable automatically opening the browser |

#### Examples

```bash
# Use the default configuration (haijunbot's config_schema.json)
haijunbot-config web

# Specify a custom schema and output file
haijunbot-config web -s config/schema.json -o config/output.json

# Specify port 3000
haijunbot-config web -s config/schema.json -o config/output.json -p 3000

# Do not automatically open the browser
haijunbot-config web -s config/schema.json -o config/output.json --no-browser
```

---

## 🛠️ JSON Schema Support

### Supported Field Types

| Type      | Description           | Example              |
| --------- | --------------------- | -------------------- |
| `string`  | String                | Username, URL        |
| `number`  | Floating-point number | Rate, ratio          |
| `integer` | Integer               | Port, count          |
| `boolean` | Boolean               | Toggle state         |
| `array`   | Array                 | Tag list             |
| `object`  | Object                | Nested configuration |

### Supported Constraints

| Constraint         | Applicable Type | Description                 |
| ------------------ | --------------- | --------------------------- |
| `required`         | All             | Required field              |
| `default`          | All             | Default value               |
| `enum`             | All             | List of enumerated values   |
| `minimum`          | number/integer  | Minimum value               |
| `maximum`          | number/integer  | Maximum value               |
| `exclusiveMinimum` | number/integer  | Strictly greater than       |
| `exclusiveMaximum` | number/integer  | Strictly less than          |
| `minLength`        | string          | Minimum length              |
| `maxLength`        | string          | Maximum length              |
| `pattern`          | string          | Regular expression          |
| `format`           | string          | Format (e.g. uri, email)    |
| `minItems`         | array           | Minimum number of items     |
| `maxItems`         | array           | Maximum number of items     |
| `items`            | array           | Array item type             |
| `properties`       | object          | Object property definitions |

### Field Type Examples

```json
{
  "properties": {
    "username": {
      "type": "string",
      "minLength": 3,
      "maxLength": 20,
      "default": "admin"
    },
    "port": {
      "type": "integer",
      "minimum": 1,
      "maximum": 65535,
      "default": 8080
    },
    "rate": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "default": 0.5
    },
    "enabled": {
      "type": "boolean",
      "default": true
    },
    "status": {
      "type": "string",
      "enum": ["active", "inactive", "pending"],
      "default": "pending"
    },
    "tags": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 0,
      "maxItems": 10,
      "default": []
    },
    "database": {
      "type": "object",
      "properties": {
        "host": { "type": "string", "default": "localhost" },
        "port": { "type": "integer", "default": 5432 }
      },
      "default": {}
    }
  }
}
```

---

## 💡 Usage Examples

### Simple Configuration

**Schema (`simple.json`)**:

```json
{
  "title": "Simple Configuration",
  "type": "object",
  "required": ["app_name", "debug_mode"],
  "properties": {
    "app_name": {
      "type": "string",
      "description": "Application name",
      "default": "my-app"
    },
    "debug_mode": {
      "type": "boolean",
      "description": "Debug mode",
      "default": false
    }
  }
}
```

**Startup Command**:

```bash
haijunbot-config web simple.json output.json
```

**Generated Configuration (`output.json`)**:

```json
{
  "app_name": "my-app",
  "debug_mode": false
}
```

---

### Complex Nested Configuration

**Schema (`complex.json`)**:

```json
{
  "title": "Complex Configuration",
  "type": "object",
  "required": ["name", "servers"],
  "properties": {
    "name": {
      "type": "string",
      "description": "Project name"
    },
    "servers": {
      "type": "array",
      "description": "Server list",
      "items": {
        "type": "object",
        "properties": {
          "host": { "type": "string" },
          "port": { "type": "integer", "minimum": 1, "maximum": 65535 }
        },
        "required": ["host", "port"]
      },
      "minItems": 1
    },
    "database": {
      "type": "object",
      "properties": {
        "driver": {
          "type": "string",
          "enum": ["postgresql", "mysql", "sqlite"]
        },
        "connection": {
          "type": "object",
          "properties": {
            "host": { "type": "string" },
            "port": { "type": "integer" },
            "username": { "type": "string" },
            "password": { "type": "string" }
          }
        }
      }
    }
  }
}
```

**Startup Command**:

```bash
haijunbot-config web complex.json config.json --port 3000
```

---

## 🎨 Design Notes

### Zen-iOS Hybrid Frontend Style

`haijunbot_config` adopts the **Zen-iOS Hybrid** design language to provide a refined user interface experience.

#### Core Design Principles

1. **Global background color**: uses iOS system gray `#F2F2F7` to eliminate pure white backgrounds
2. **Extreme frosted glass**: layered containers use `backdrop-blur-40px` to `60px` with a semi-transparent background `White/40-60`
3. **Double-layer physical stroke**:
   - Inner stroke: `1px border-white/60` (simulates the light of a glass edge)
   - Outer stroke: `1px border-gray-200/40` (defines the physical outline)
4. **Deep shadow**: floating components use a soft diffuse shadow `shadow-[0_24px_48px_-12px_rgba(0,0,0,0.08)]`
5. **Rounded-corner aesthetics**:
   - Large containers: `rounded-[40px]` to `[50px]`
   - Functional blocks: `rounded-[28px]`
   - Small components: `rounded-xl`
6. **Haptic feedback**: all clickable items have an `active:scale-95` physical bounce

#### Component Styles

- **Primary button**: deep space black `#1C1C1E`, high contrast to guide the user's attention
- **Input field**: recessed effect with `shadow-inner` and a light gray background
- **Toggle**: iOS-style green switch `#34C759`
- **Spacing**: enforces large spacing `p-6` or `p-8` to ensure a sense of breathing room

#### Font System

- Uses the **Inter** or **SF Pro Display** font
- Headings: `Font-Extrabold` + `Tracking-tight`
- Labels: all uppercase + `Tracking-widest` + `Font-Bold` + `text-[10px]`

---

## 🔧 API Endpoints

### GET `/api/schema`

Retrieves schema data and metadata.

**Response Example**:

```json
{
  "title": "Application Configuration",
  "description": "Basic configuration for the application",
  "properties": {
    "name": {
      "type": "string",
      "_meta": {
        "description": "Application name",
        "default": "my-app",
        "required": true
      }
    }
  },
  "required": ["name"]
}
```

### POST `/api/save`

Saves and validates the configuration data. Automatically saves as JSON or YAML format based on the output file extension.

**Request Body**:

```json
{
  "config": {
    "name": "my-app",
    "port": 8080
  }
}
```

**Response Example (success)**:

```json
{
  "success": true,
  "message": "Configuration saved to /path/to/config.json",
  "path": "/path/to/config.json"
}
```

**Note**: if the output file extension is `.yaml` or `.yml`, the configuration will be saved in YAML format; otherwise it will be saved in JSON format.

**Response Example (validation failed)**:

```json
{
  "success": false,
  "errors": [
    {
      "path": "name",
      "message": "String length 0 is less than minimum 1"
    }
  ]
}
```

### GET `/api/health`

Health check endpoint.

**Response Example**:

```json
{
  "status": "ok"
}
```

---

## 🔗 Relationship with the Embedded Configuration Editor in the Web UI

In addition to the standalone CLI tool `haijunbot-config` introduced on this page, HaijunBot's Web UI also has a built-in configuration file editor. Both dynamically generate forms based on the same `config_schema.json`, but their running methods and endpoints differ:

| Item           | Standalone CLI tool (`haijunbot-config web`)                         | Embedded editor in the Web UI                               |
| -------------- | ----------------------------------------------------------------- | ----------------------------------------------------------- |
| Startup method | Execute a command in the terminal to start the service separately | No separate startup; provided along with the Web Gateway    |
| Entry point    | Access the address printed by the CLI in a browser                | "Config File Editing" in the "Settings" popup of the Web UI |
| Schema         | `GET /api/schema`                                                 | `GET /api/config/schema`                                    |
| Save           | `POST /api/save`                                                  | `POST /api/nodes/{node_id}/config`                          |
| Permissions    | No additional permission requirements (separate local service)    | Requires the `admin:config` permission                      |
| Plain text     | No separate plain-text view                                       | Provides dual "Form / Plain text" views                     |

If you are already connected to the Web Gateway, it is recommended to use the embedded editor directly; if you want to edit arbitrary Schemas and output files in a separate local service, use `haijunbot-config web`.

For detailed steps of the embedded editor, see: [Editing Configuration Files in the Web UI](user-manual/04_web-ui-and-gateway/Editing_Config_Files_in_the_Web_UI.md).

---

## 📝 Notes

1. **Schema version**: supports the JSON Schema Draft-07 specification
2. **Output directory**: if the parent directory of the output file does not exist, it will be created automatically
3. **Validation rules**: the configuration is validated against the Schema when saving; a validation failure returns error details
4. **Browser support**: modern browsers are recommended (latest versions of Chrome, Firefox, Safari, Edge)

---

## 🤝 Contributing

Issues and Pull Requests are welcome!

---

## 📄 License

MIT License
