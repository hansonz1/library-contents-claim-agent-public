# Evaluation

The test scope is 27 books in a cabinet. [Ground truth and recorded quotes](ground-truth.csv) contain the hand-read titles and manual spine measurements. The listing prices are user-supplied and may need edition or condition verification. See [title-by-title photo review](../inventory-review.md).

| Metric | Assignment target | Observed result |
|---|---|---|
| Book count | Within 5% | Manual count: 27. The sweep produced nine title candidates. Physical count accuracy was not measured. |
| Title ID | At least 70% of legible spines correct, at most 3% confidently wrong | Two photos: 15/27 exact-title matches. After targeted recapture: 18/27 (66.7%). One wrong title appeared in the initial photo results, and a separate live sweep had one human-corrected candidate. No confidence threshold was applied, so confidently wrong rate is unverified. |
| Spine dimensions | Within 15% on a 20-book hand-measured sample | Three thickness trials and one height trial. One book's height error was 1.90% and thickness error 4.22%. The 20-book system comparison is incomplete. |
| Book prices | Within 25% on 15 hand-checked books, same source type | One same-ISBN US retail pilot. New price deviation 4.8%. Used Good deviation 36.2%, using an independent marketplace offer. No formal 15-book pass result. |
| Second market | Same 10 books priced in a second country | Not evaluated. |
| Non-book contents | At least 80% correctly categorized | Not evaluated. |
| Floor and wall area | Within 10% and 15%, respectively | Not measured. |
| Packet time | Under 5 minutes after sweep | JSON and HTML export verified. Timing from completed sweep to finished packet was not measured. |

The [combined report](claim/report.html) retains three frames from one sweep. Nine reviewed titles link to those frames. The other 18 inventory entries have no frame match in that sweep. Manual quotes total $304.03 across 20 new offers and $83.01 across 18 used offers. Seven books have no quote. These are spreadsheet subtotals, excluding taxes and shipping.

The public release keeps frame identifiers and transcripts. Original images are withheld and retained in the private submission.
