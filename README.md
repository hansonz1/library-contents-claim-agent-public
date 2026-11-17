# Library Contents Claim Agent

A browser-based prototype that captures bookshelf frames, streams them through FastAPI to Gemini Live, and displays spoken feedback and candidate book titles. The public release includes the 27-book evaluation and a sample claim packet. Original camera images are retained in the private submission.

## 1. Clone and install

Prerequisites: Python 3.11+, Git, and a recent Chrome browser. Live features also need a Gemini API key and permission to use the camera and microphone.

```sh
git clone https://github.com/hansonz1/library-contents-claim-agent-public.git
cd library-contents-claim-agent-public
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest -v
```

On Windows PowerShell, create the environment with `py -3 -m venv .venv` and replace `.venv/bin/python` in the following commands with `.\.venv\Scripts\python.exe`.

## 2. Run the offline smoke test

```sh
.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) and click **Load mock inventory**. Expect 27 synthetic titles. The mixed-language sample records exercise Unicode handling. This mode uses no API key and sends no requests to Gemini.

## 3. Enable Gemini Live

1. Stop the local server with **Ctrl+C**.
2. Create a key in [Google AI Studio](https://aistudio.google.com/app/api-keys). Check that the project can access `gemini-3.8-live`. To stay within free usage, use a project with billing disabled and check its active quota.
3. Set the key in the same terminal that will run FastAPI. The server reads the environment variable directly. The browser never receives it. On macOS zsh:

   ```zsh
   read -rs 'GEMINI_API_KEY?Paste your Gemini API key and press Enter: '
   export GEMINI_API_KEY
   ```

   On Windows PowerShell 7, use `$env:GEMINI_API_KEY = Read-Host -MaskInput "Gemini API key"`.

4. Verify the connection with `.venv/bin/python check_live.py`. Expect `Gemini Live handshake OK`.
5. Start FastAPI again using the command in Step 2. Refresh the page. **Test Live** should show a short transcript.

If the server reports a missing key, start it from the same terminal where you set the variable. If the browser cannot connect, confirm that the terminal shows startup complete and that the address uses `127.0.0.1:8000`.

## 4. Capture and review a sweep

1. Click **Start preview** and allow camera and microphone access. Aim the camera at book spines. Keep people and personal documents out of view.
2. To test a spoken question, check **Pause after first frame for a voice question**. Click **Start sweep**.
3. Wait for the first frame feedback. If you enabled voice, click **Ask Gemini · 4 seconds** and ask, “What book did you see?” Check the **Heard** and **Reply** fields.
4. Watch **Live inventory** for candidate titles. The same normalized title can link to multiple frames. The prototype sends up to three frames within 60 seconds.
5. Click **Stop sweep** if the run is still active, then **Download sweep evidence**. Click **Stop preview** to release the camera and microphone.

## 5. Export the claim packet

Replace `/path/to/sweep.json` with the downloaded file path. Use a new output directory.

```sh
.venv/bin/python export_claim.py "/path/to/sweep.json" draft-packet --country US --currency USD
```

Open `draft-packet/report.html`. Follow a frame link to inspect the source image and compare it with the recorded transcript or candidate. The export also includes `claim_packet.json` and the JPEG evidence. The sample combined report uses recorded manual US quotes. New sweeps do not fetch Amazon prices automatically.

For the spine calibration tool, open [http://127.0.0.1:8000/measure](http://127.0.0.1:8000/measure), load a photo with a ruler in the same plane as the spine, and click two ruler ticks followed by two spine edges along the same axis. Enter the known distance between ticks. The photo stays in your browser.

## Scope of this take-home

This prototype was developed within the assignment's 48-hour window. It demonstrates a short bookshelf sweep, Gemini Live voice feedback and questions, candidate book identification, and claim packet export. The evaluation and failure log document which checks were completed and which requirements remain open.

## Evaluation and limitations

- [Evaluation results](submission/EVALUATION.md) and [manual baseline](submission/ground-truth.csv)
- [Sample claim report](submission/claim/report.html) and [structured JSON](submission/claim/claim_packet.json)
- [Architecture](submission/ARCHITECTURE.md) and [failure log](submission/FAILURE-LOG.md)

The prototype was evaluated on a 27-book cabinet. It supports short sampled sweeps, with no completed room-area measurement or unedited demonstration video. Voice correction remains experimental. The upstream example documentation was reviewed, and the upstream application was not run before implementation. This public repository contains evidence identifiers and transcripts. The private submission retains original images.
