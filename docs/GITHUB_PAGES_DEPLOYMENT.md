# GitHub Pages Deployment Guide

This document explains how to use MkDocs to build and deploy GitHub Pages for the HaijunBot project.

## 📋 Overview

This project uses [MkDocs](https://www.mkdocs.org/) + [Material Theme](https://squidfunk.github.io/mkdocs-material/) to build the documentation site, and automatically deploys it to GitHub Pages via GitHub Actions.

## 🚀 Local Preview

### Install Dependencies

```bash
pip install -r requirements-docs.txt
```

Or install manually:

```bash
pip install mkdocs-material
pip install mkdocs-git-revision-date-localized-plugin
pip install pymdown-extensions
```

### Start the Local Server

```bash
mkdocs serve
```

Visit <http://127.0.0.1:8000> to preview the documentation.

### Build the Static Site

```bash
mkdocs build
```

The generated static files will be saved in the `site/` directory.

## 🔧 Automatic GitHub Pages Deployment

### Configuration Description

The project has configured the GitHub Actions workflow `.github/workflows/deploy-docs.yml`, which automatically triggers deployment when the following situations occur:

- Pushing code to the `main` or `master` branch
- Submitting a Pull Request to the `main` or `master` branch

### Enable GitHub Pages

Manual enablement of GitHub Pages is required for first-time use:

1. Go to the repository's **Settings** page
2. Select **Pages** in the left menu
3. In the **Build and deployment** section:
   - **Source**: select `GitHub Actions`
4. Save the settings

### Deployment Flow

1. Push code to the `main` branch
2. GitHub Actions automatically triggers the build
3. After the build completes, it automatically deploys to GitHub Pages
4. Visit `https://<username>.github.io/<repository>/` to view the deployment result

### View Deployment Status

- View the build and deployment status on the repository's **Actions** tab
- A green check mark is displayed after successful deployment
- If it fails, click the failed task to view detailed logs

## 📂 Project Structure

```text
HaijunBot/
├── docs/                      # Documentation source files
│   ├── haijunbot_book/          # Main documentation
│   ├── best_practices/       # Best practices
│   ├── compare/              # Comparison analysis
│   └── GITHUB_PAGES_DEPLOYMENT.md  # This document
├── .github/
│   └── workflows/
│       └── deploy-docs.yml   # GitHub Actions workflow
├── mkdocs.yml                # MkDocs configuration file
└── requirements-docs.txt     # Documentation dependencies
```

## 🎨 Custom Configuration

### Modify Configuration

Editing the `mkdocs.yml` file allows you to customize:

- **Theme colors**: modify the `theme.palette` section
- **Navigation structure**: modify the `nav` section
- **Plugins**: add or remove plugins in the `plugins` section
- **Markdown extensions**: configure in the `markdown_extensions` section

### Update Repository Information

Modify the following configuration in `mkdocs.yml` to your actual repository information:

```yaml
definition:
  github:
    repo_url: https://github.com/your-username/haijunbot
    edit_uri: edit/main/docs/

extra:
  social:
    - icon: fontawesome/brands/github
      link: https://github.com/your-username/haijunbot
```

## 🔍 Features

- ✅ Responsive design with mobile support
- ✅ Dark/light theme switching
- ✅ Smart search (supports Chinese)
- ✅ Code highlighting and copy button
- ✅ Automatic table of contents generation
- ✅ Git revision date display
- ✅ Tab support
- ✅ Task list support
- ✅ Math formula rendering
- ✅ Mermaid diagram support

## 📚 Related Resources

- [MkDocs Official Documentation](https://www.mkdocs.org/)
- [Material Theme Documentation](https://squidfunk.github.io/mkdocs-material/)
- [GitHub Pages Documentation](https://docs.github.com/en/pages)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

## 🐛 FAQ

### Q: Local preview works fine, but the styles are broken after deployment?

A: Clear your browser cache or access it in private/incognito mode.

### Q: The search feature doesn't work?

A: Make sure the search plugin is enabled in `mkdocs.yml` and that the site has been fully deployed.

### Q: How do I add a new page?

A: Add a Markdown file under the `docs/` directory and add a navigation link in the `nav` section of `mkdocs.yml`.

### Q: What should I do if deployment fails?

A: Check the detailed logs on the GitHub Actions page and look for syntax errors or dependency issues.

## 📝 Maintenance Recommendations

1. **Regularly update dependencies**: regularly run `pip install -U mkdocs-material` to update the theme
2. **Test the build**: run `mkdocs build` locally before pushing to make sure there are no errors
3. **Check links**: regularly check whether the links in the documentation are valid
4. **Back up configuration**: back up the `mkdocs.yml` configuration file before important changes

---

If you have any questions or suggestions, feel free to submit an Issue or Pull Request!
