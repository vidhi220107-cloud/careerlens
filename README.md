# Career Aspiration & Skill Gap Analysis for Youth

**Community Engagement Program (CEP) · Topic 14**

CareerLens is a Streamlit-based survey analysis prototype that explores career aspirations, self-rated skills, career-guidance access, employment-readiness concerns and requested support among youth respondents.

## Features

- Upload a genuine Google Forms survey export as CSV.
- Explore career aspirations and preferred career directions.
- Compare self-reported skill ratings on a 1–5 scale.
- Review reported barriers, career guidance and support needs.
- Generate practical, sample-based action suggestions.
- Search, filter and download visible survey data.
- Review missing values and column completeness.

## Run locally (Windows PowerShell)

1. Extract the project folder and open PowerShell in that folder.
2. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Start the app:

   ```powershell
   python -m streamlit run app.py
   ```

5. Upload the genuine survey CSV using the uploader in the sidebar. For a quick demonstration, the included `survey_responses.csv` can be loaded from the Overview page.

## Data and interpretation notes

- The included CSV contains the project's collected survey responses; no synthetic respondents are added by the app.
- Findings describe only the uploaded sample and should not be generalized to all youth.
- Skill values are self-reported ratings, not objective assessments of competence.
- Blank responses are not silently imputed. Review the data-quality section before interpreting results.
- Identifying fields are hidden from the Explore Data preview by default. Handle survey data responsibly.

## Pages

1. Upload & Overview
2. Career Aspirations
3. Skill Gap Analysis
4. Guidance & Barriers
5. Recommended Action Plan
6. Explore Survey Data

## Technology stack

Python · Streamlit · Pandas · Plotly
