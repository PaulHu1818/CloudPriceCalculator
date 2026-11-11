# Publish to Streamlit Community Cloud

1. Create a **GitHub repository** and upload the contents of this folder to the repository root. Do not upload the `.rar` file or `__pycache__`.
2. Open https://share.streamlit.io/ and sign in with GitHub.
3. Select **Create app** → **Deploy a public app from GitHub**.
4. Choose the repository and branch; set **Main file path** to `app.py`.
5. Choose a public app URL, then deploy. No secrets are required.
6. Check the **Lab 7 final comparison** page: AWS $1,352.06/month, Azure $1,467.05/month (modeled), GCP $1,217.25/month (modeled).

## Important distinctions

The first page is a **fixed assignment comparison**, built from the uploaded AWS official calculator export and hypothetical Azure/GCP category factors. It is not a vendor-validated comparison. The other app pages retain the original independent interactive planning model; sidebar changes do not change the fixed assignment comparison.

The original README described a Windows launcher and tests that were not included in the uploaded RAR. Use `python -m pip install -r requirements.txt` and `python -m streamlit run app.py` for local execution.
