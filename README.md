# ABCover Multi-Agent System (LLM-Powered)

An intelligent, agentic AI system for analyzing school absence data and calculating insurance premiums using LLM-powered agents that can reason and adapt to school-specific requirements.

## Features

- **LLM-Powered Agents**: Agents use Large Language Models to reason about data and calculations
- **Adaptive Logic**: Calculations adapt based on school-specific patterns and requirements
- **Intelligent Analysis**: Agents analyze data structure and suggest appropriate cleaning rules
- **Reasoning**: Agents explain their calculation decisions and reasoning

## Architecture

### Agents

1. **FileUploadAgent**: Handles CSV/Excel file uploads (deterministic)
2. **DataSelectionAgent**: Column/row selection (deterministic)
3. **DataAnalysisAgent** (LLM): Analyzes data structure and suggests cleaning rules
4. **DataCleaningAgent**: Applies cleaning rules (deterministic, but rules can come from LLM)
5. **RatingEngineAgentLLM** (LLM): Reasons about calculations and adapts to school-specific logic

### Orchestration

- **Pattern**: Sequential Pipeline with LLM Reasoning
- **Orchestrator**: Streamlit App
- **LLM Integration**: LangChain with OpenAI or Anthropic

## Setup

### 1. Install Dependencies

```bash
# Activate virtual environment
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### 2. Configure LLM

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your API key:

**Option 1: OpenAI**
```env
OPENAI_API_KEY=your_openai_api_key_here
```

**Option 2: Anthropic (Claude)**
```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### 3. Run the Application

**Activate the virtual environment first**, then run the app:

```bash
# Activate venv (required)
source venv/bin/activate   # macOS/Linux
# On Windows: venv\Scripts\activate

# Run the app
streamlit run app.py
```

Then open http://localhost:8501. Use **Create account** (with an @abcover.org email) to sign up, or **Log in** if you already have an account.

## How It Works

1. **Upload File**: User uploads school absence data
2. **Data Analysis** (LLM): Agent analyzes data structure and suggests cleaning rules
3. **Data Selection**: User selects columns and filters rows
4. **Data Cleaning**: Apply cleaning rules (can be LLM-suggested)
5. **Rating Engine** (LLM): Agent reasons about calculation approach and calculates premium
6. **Results**: Display results with LLM explanations

## LLM Agents Explained

### DataAnalysisAgent
- Analyzes uploaded data structure
- Identifies data quality issues
- Suggests school-specific cleaning rules
- Reasons about data patterns

### RatingEngineAgentLLM
- Understands Rating Engine logic from Excel template
- Reasons about school-specific calculation differences
- Adapts calculation approach based on data characteristics
- Explains calculation decisions

## Why LLM-Powered?

Different schools may have:
- Different absence calculation rules
- Different employee type classifications
- Different coverage interpretations
- School-specific business logic

LLM agents can reason about these differences and adapt calculations accordingly, just like a human analyst would.

## Requirements

- Python 3.8+
- OpenAI API key OR Anthropic API key
- Streamlit
- LangChain

## Project Structure

```
ABCover/
├── agents/
│   ├── llm_agent_base.py          # Base class for LLM agents
│   ├── data_analysis_agent.py     # LLM agent for data analysis
│   ├── rating_engine_agent_llm.py # LLM agent for calculations
│   ├── file_upload_agent.py       # File upload (deterministic)
│   ├── data_selection_agent.py    # Data selection (deterministic)
│   └── data_cleaning_agent.py     # Data cleaning (deterministic)
├── app.py                          # Main Streamlit app
├── requirements.txt                # Dependencies
└── .env                            # API keys (create this)
```
