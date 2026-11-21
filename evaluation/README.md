# Evaluating Whether the AI Understands the Real Sentiment

A model can get the right label for the wrong reason, or the wrong label for an
understandable reason. To judge *understanding*, compare its output against human labels
on several dimensions, not only the final verdict.

## 1. Build a labeled test set

`test_sentences.csv` holds starter sentences grouped by category. For each one, write
down **before running the model**:

- `human_sentiment`: positive / negative / neutral / mixed
- `human_polarity`: -1.0 to +1.0
- `sarcasm`: yes / no
- `notes`: what the writer really means

Ideally, have 2-3 people label each sentence on their own. Where humans disagree, the
sentence is truly ambiguous. The model should flag that too, rather than sound certain.

## 2. Score each response

| Dimension | Question to ask | Score |
|---|---|---|
| **Verdict accuracy** | Does `intended_sentiment` match the human label? | 0 / 1 |
| **Polarity closeness** | `1 - abs(model_polarity - human_polarity) / 2` | 0-1 |
| **Sarcasm detection** | Does `sarcasm_or_irony_detected` match? | 0 / 1 |
| **Emoji interpretation** | Is each `contextual_meaning` right for this context, not just the dictionary meaning? | 0-2 |
| **Reasoning quality** | Does the explanation give the *right reason*, with no invented context? | 0-2 |
| **Calibration** | High confidence on clear cases and low confidence on ambiguous ones? | 0-2 |

**Understanding score per sentence** = sum ÷ 9 (maximum).

## 3. Signs of real understanding vs. surface matching

**Real understanding:**
- Reads 💀 / 😭 / 🙃 / 🙂 differently depending on context
- Catches sarcasm when positive emojis sit on top of negative events
- Spots mixed emotions (e.g. bittersweet goodbyes)
- Lowers its confidence and lists alternatives when the meaning is truly unclear
- Changes its answer when you supply context that should change it

**Surface matching:**
- Maps emojis to fixed sentiments (😂 = always happy, 😭 = always sad)
- `text_only_analysis` and `final_verdict` are always the same, so the emojis are ignored
- High confidence on everything
- Reasoning restates the label without explaining *why*

## 4. Useful experiments

1. **Emoji ablation:** run the same sentence with no emojis, with the original emojis,
   and with swapped emojis (e.g. `I got the job 😭` vs `I got the job 😢`). Check that the
   verdict moves the way a human would expect.
2. **Context flip:** run an ambiguous sentence with two different context lines and see
   if the verdict changes appropriately.
3. **Consistency:** run each sentence 3 times. Unstable verdicts on clear sentences point
   to weak understanding.
4. **Cross-model:** run the same prompt on several models and compare understanding scores.
