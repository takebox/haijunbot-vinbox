---
name: macos-web-design
description: Triggered when a macOS-style web interface needs to be designed or the Apple design language needs to be implemented. Triggered whenever the user mentions "macOS style", "Apple design", "macOS UI", "Apple style", "macOS interface", "Vision Pro", "visionOS". Not triggered: only designing a dark theme (use the dark-theme-design rules); only designing a light theme (use the light-theme-design rules); only discussing UI design without macOS style involvement.
---

# macOS Style Web Design Standards

## Design Language

### Core Principles

- **Simple and elegant**: Follow Apple's design philosophy and pursue ultimate simplicity
- **Material texture**: Make good use of material effects such as frosted glass and translucency
- **Fluid animations**: Use smooth transitions and spring animations
- **Spatial layering**: Use shadows and blur to create a sense of depth

### Color System

- **System colors**: Use Apple system colors (system blue, system red, etc.)
- **Background colors**: Light gray for light mode (`#f5f5f7`), dark gray for dark mode (`#1c1c1e`)
- **Accent color**: Use Apple blue (`#007aff`)

## Component Standards

### Windows

- Corner radius: large radius (12–16px)
- Title bar: includes the three red, yellow, and green window control buttons
- Shadow: soft, diffuse shadow
- Toolbar: semi-transparent frosted glass

### Buttons

- **System buttons**: text buttons, no border
- **Push buttons**: blue fill, white text
- **Circular buttons**: used for icon actions

### Forms

- Input: rounded rectangle, blue border on focus
- Selector: native-style dropdown menu
- Slider: system-style slider
- Toggle: iOS-style switch

### Navigation

- **Sidebar**: semi-transparent frosted glass effect
- **Tab bar**: icons plus text
- **Breadcrumbs**: system font, arrow separators

## Typography Standards

- **System font**: SF Pro or Inter
- **Large title**: Large Title (34px)
- **Subtitle**: Title 2 (22px)
- **Body text**: Body (17px)
- **Footnote**: Footnote (13px)

## Animation Standards

- **Duration**: 0.2–0.4s
- **Easing function**: `cubic-bezier(0.25, 0.1, 0.25, 1)`
- **Spring animations**: use spring animations
- **Transitions**: a combination of opacity and translation

## Checklist

- [ ] Use Apple system colors
- [ ] Windows have the red, yellow, and green control buttons
- [ ] Use frosted glass effects
- [ ] Animations are smooth and natural
- [ ] Use system fonts
- [ ] Corner radius values are consistent
- [ ] Shadows are soft
