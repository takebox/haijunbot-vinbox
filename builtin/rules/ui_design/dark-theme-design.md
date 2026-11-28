---
name: dark-theme-design
description: Triggered when a dark theme UI needs to be designed or dark mode needs to be implemented. Triggered whenever the user mentions "dark theme", "dark mode", "deep color theme", "night mode", "dark black mode", "Dark Mode", "Dark Theme". Not triggered: only designing a light theme (use the light-theme-design rules); only discussing UI design without theme involvement; only implementing functionality without UI involvement.
---

# Dark Theme Design Standards

## Color System

### Background Colors

- **Primary background**: Dark gray (`#1a1a2e` or similar)
- **Secondary background**: Slightly lighter than the primary background (`#16213e`)
- **Card background**: One more shade lighter (`#0f3460`)
- **Input background**: Dark (`#0d1b2a`)

### Text Colors

- **Primary text**: High-contrast white (`#e0e0e0`)
- **Secondary text**: Medium-contrast gray (`#a0a0a0`)
- **Disabled text**: Low-contrast dark gray (`#606060`)
- **Link text**: Bright blue (`#64b5f6`)

### Accent Colors

- **Primary color**: Keep the brand color, but reduce saturation appropriately
- **Success**: Soft green (`#4caf50`)
- **Warning**: Soft orange (`#ff9800`)
- **Error**: Soft red (`#f44336`)
- **Info**: Soft blue (`#2196f3`)

## Design Principles

- **Reduce glare**: Avoid pure black backgrounds and use dark gray instead
- **Ensure contrast**: Text-to-background contrast ≥ 4.5:1
- **Soft shadows**: Use semi-transparent shadows rather than pure black shadows
- **Eye comfort**: Reduce the amount of blue light to ease eye strain

## Component Adaptation

### Navigation Bar

- Background: primary background color
- Hover: use a semi-transparent highlight
- Selected: use the accent color

### Buttons

- Default: filled with the primary color
- Hover: slightly increased brightness
- Disabled: reduced opacity

### Forms

- Input: dark background, light border
- Focused: border changes to the accent color
- Error: border changes to red

### Modal Dialogs

- Overlay: semi-transparent black (`rgba(0,0,0,0.5)`)
- Content area: secondary background color

## Checklist

- [ ] Backgrounds use dark gray rather than pure black
- [ ] Text contrast meets the standard
- [ ] Accent colors have reduced saturation
- [ ] Shadows are semi-transparent
- [ ] Components are adapted to dark mode
- [ ] Transition animations are smooth
