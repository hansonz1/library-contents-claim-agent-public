# Failure log

| Failure | Observed cause or limitation | Change and measured result |
|---|---|---|
| A frame returned no books, and another misread 麦肯锡方法 as 西方哲学史. | The evidence contains an empty view in frame 1. The model's specific reason for misreading frame 2 is unknown. It supplied a title without enough evidence. | Preserve frame links and require review on uncertainty. The reviewer corrected the title. In a separate photo-based trial, targeted recapture increased full matches from 15/27 to 18/27. |
| Voice-based title correction timed out. | The dedicated correction test timed out waiting for Gemini. The underlying cause was not isolated. | Chunking PCM and explicitly marking voice activity did not establish a successful correction test. In-sweep voice Q&A succeeded separately. Next, record send, first-response and completion events on the correction path. |
| Thin-spine width changed with edge choice. | A few pixels are a larger fraction of a narrow spine. The snapper follows local color contrast and can shift an already accurate point. | With the same clicks, snapping reduced one thickness error from 18.48% to 7.67% and increased another from 1.46% to 4.06%. Snapping stays optional. |

**Measured timing.** The inventory-evidence sweep lasted **41.114 s**. Browser send-to-feedback times were **3.432 s**, **16.415 s**, and **17.610 s** for frames 1–3. Each includes network, model processing and browser receipt. Separate service-stage and packet-generation latency were not instrumented. Actual API cost per sweep was not recorded. Local mock mode makes no API calls.

**Next two weeks.** Test a continuous phone sweep, distinguish identical book copies by shelf position, add reproducible scale capture, and benchmark sourced prices against same-edition, same-condition listings. Instrument latency and billed usage before making cost or throughput claims.
