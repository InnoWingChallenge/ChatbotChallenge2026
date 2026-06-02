# InnoWing Chatbot Challenge
This is a testing repository.

## 📦 Requirements

### **General**

*   Git
*   A code editor (VS Code recommended)

### **Python Setup**

*   Python **3.9+**
*   `pip` for dependency installation

## 🚀 Getting Started

Clone the repository:

```bash
git clone https://github.com/HKUGenAI/InnoWingChatbotChallenge-test.git
cd InnoWingChatbotChallenge-test
```

## 🐍 Python Setup

### 1. Create and activate a virtual environment

```bash
# macOS & Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set environment variables

```bash
cp .env.example .env
```

### 4. Run the chatbot

```bash
python api.py
```

You should see the reply to an example chat. Below are the details of the example messages:

User: "Does Azure OpenAI support customer managed keys?"

AI: "Yes, customer managed keys are supported by Azure OpenAI."

User: "Do other Azure AI services support this too?"

AI: ... (the answer you see)
