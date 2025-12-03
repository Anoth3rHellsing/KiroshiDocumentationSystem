# Kiroshi Documentation System

[![Version](https://img.shields.io/badge/version-Release%201.8.0-blue)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Kiroshi is a comprehensive IT case documentation tool built with **Streamlit**. It streamlines support workflows by providing a structured workspace for tracking cases, generating professional email drafts, creating PDF reports, and leveraging AI assistance for troubleshooting and QA.

---

## 🚀 Quick Start

### Prerequisites

*   **Python 3.10+ (64-bit)** recommended.
*   **Git** (optional, for cloning).

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/YourOrg/KiroshiDocumentationSystem.git
    cd KiroshiDocumentationSystem
    ```

2.  **Create a virtual environment (Recommended):**
    ```bash
    # Windows (PowerShell)
    python -m venv .venv
    .\.venv\Scripts\activate

    # macOS/Linux
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Optional)* For local AI models and mini-games, install additional requirements:
    ```bash
    pip install -r requirements-bored.txt
    ```

### Running the Application

To launch Kiroshi, run the following command in your terminal:

```bash
streamlit run case_documentation_app.py
```

Or use the provided wrapper script:

```bash
python run_app.py
```

The application will open in your default web browser (typically at `http://localhost:8501`).

---

## ✨ Key Features

### 🖥️ Dashboard & Operations
*   **Tracked Cases:** Monitor ongoing cases with priority badges (Low, Normal, High, Critical).
*   **Specialized Queues:** Dedicated tables for **Dell Escalations** and **FedEx Replacements**.
*   **Sprint View:** A task execution board for organizing your daily workload using agile principles.
*   **Saved Cases:** Searchable index of all historical cases stored in the database.

### 📂 Case Workspace
Each case opens in a dedicated tab with powerful tools:
*   **Quick Actions:** Floating menu for one-click Save, Tracking, and AI tools.
*   **Documentation Forms:** Structured fields for customer details, troubleshooting notes, and hardware specs.
*   **Remote Session Log:** Unified timeline for tracking remote interventions and credentials.
*   **Email Generator:** Templates for customer recaps, escalations, and hardware replacements.
*   **Tables & Exports:** Copy Excel-ready tables or download full PDF case summaries.

### 🤖 AI Power Tools
*   **AI Assistance:** Get concise troubleshooting guidance based on case details.
*   **AI Autocorrect:** Polish your notes for QA compliance and clarity.
*   **Categorizer:** Automatically suggest the correct Product/Topic/Subtopic classification.
*   **QA Verify:** Score your case documentation against support quality standards.
*   **Smart Aid:** Persistent supervisor feedback reminders across the AI suite.

### ☁️ Kiroshi Cloud & Settings
*   **Cloud Sync:** Synchronize your AI Educate knowledge base with the team.
*   **Settings:** Configure 2nd Line Mode, Dark Mode, Wellness Reminders, and more.
*   **Update Manager:** Built-in check for repository updates.

---

## 🎹 Global Hotkeys

Kiroshi includes a background listener for global clipboard shortcuts (Windows only).

| Shortcut | Action |
| :--- | :--- |
| **Ctrl+Alt+1** | Copy Case Title |
| **Ctrl+Alt+2** | Copy Description Table |
| **Ctrl+Alt+3** | Copy Phonecall Table |
| **Ctrl+Alt+4** | Copy Internal Notes |
| **Ctrl+Alt+C** | Copy **All** Tables |

*Enable "Use this case for global clipboard hotkeys" in the **Tables** tab to select the active case source.*

---

## 🛠️ Project Structure

The codebase has been modularized for better maintainability:

*   **`KiroshiApp/`**: Core application package.
    *   **`models/`**: Data classes (`CaseData`, `TrackingData`, etc.).
    *   **`services/`**: Business logic (`data_manager`, `email_generator`, `pdf_generator`, etc.).
    *   **`views/`**: UI components (`case_view`, `dashboard_view`, `settings_view`, `sprint_view`).
    *   **`utils.py`**: Helper functions and constants.
*   **`case_documentation_app.py`**: Main entry point.
*   **`kiroshi_hotkeys.py`**: Background listener service for global shortcuts.

---

## 🤝 Contributing

1.  Fork the repository.
2.  Create a feature branch (`git checkout -b feature/NewThing`).
3.  Commit your changes.
4.  Push to the branch and open a Pull Request.

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
