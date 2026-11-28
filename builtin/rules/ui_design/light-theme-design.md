---
name: light-theme-design
description: Triggered when a light theme UI needs to be designed or light mode needs to be implemented. Triggered whenever the user mentions "light theme", "light mode", "light color theme", "daytime mode", "Light Mode", "Light Theme". Not triggered: only designing a dark theme (use the dark-theme-design rules); only discussing UI design without theme involvement; only implementing functionality without UI involvement.
---

# Light Theme Design Standards

## Color System

### Background Colors

- **Primary background**: Pure white or near-white (`#ffffff` or `#fafafa`)
- **Secondary background**: Light gray (`#f5f5f5`)
- **Card background**: Pure white (`#ffffff`)
- **Input background**: Light gray (`#f0f0f0`)

### Text Colors

- **Primary text**: High-contrast black (`#1a1a1a`)
- **Secondary text**: Medium-contrast gray (`#666666`)
- **Disabled text**: Low-contrast light gray (`#b0b0b0`)
- **Link text**: Blue (`#1976d2`)

### Accent Colors

- **Primary color**: Keep the brand color
- **Success**: Green (`#4caf50`)
- **Warning**: Orange (`#ff9800`)
- **Error**: Red (`#f44336`)
- **Info**: Blue (`#2196f3`)

## Design Principles

- **Clean and clear**: Keep the interface tidy and avoid visual clutter
- **Plenty of whitespace**: Use sufficient margins and spacing
- **Soft shadows**: Use light, semi-transparent shadows that do not overpower the content
- **High readability**: Ensure the contrast between text and background is ≥ 4.5:1

## Component Adaptation

### Navigation Bar

- Background: primary background color
- Bottom divider: light separator
- Selected state: use the accent color

### Buttons

- Default: filled with the primary color
- Hover: slightly reduced brightness
- Disabled: reduced opacity

### Forms

- Input: light background, dark border
- Focused: border changes to the accent color
- Error: border changes to red

### Modal Dialogs

- Overlay: semi-transparent black (`rgba(0,0,0,0.3)`)
- Content area: pure white background

## Checklist

- [ ] Background colors use white or near-white
- [ ] Text contrast meets the standard
- [ ] Shadows are soft and semi-transparent
- [ ] Components are adapted to light mode
- [ ] The interface is clean and clear
- [ ] Transition animations are smooth
