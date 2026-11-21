# Why This Matters

State actors run networks of fake accounts to spread propaganda, and they now use AI to reword each post so the network is harder to trace. This project finds those networks by how the accounts behave, not by how they write, so AI rewording doesn't hide them.

## The problem is real
- **It has changed an election.** In 2024 Romania annulled its presidential first round after intelligence linked about 25,000 coordinated TikTok accounts to a pro-Russian campaign. The candidate went from under 1% in the polls to first place.
- **It's big and organized.** Meta removed more than 7,700 accounts from China's Spamouflage network, its largest takedown ever. The accounts posted on an office-hours schedule in China's time zone.
- **They already use AI.** OpenAI reports that Russian and Chinese operations use its models to write posts in many languages.

## Why current detection fails
- **Copy-paste used to give networks away.** AI rewording removes the duplicate text.
- **Reworded propaganda works better.** In a 1,200-person study, AI-paraphrased messages made false claims seem widely believed, and AI-text detectors missed them.
- **AI-text detectors break.** Over 90% accuracy on raw AI text drops sharply once the text is paraphrased.

**Our approach:** don't ask "was this written by AI?" Ask "are these accounts working together?"

## How we detect coordination
We use no text model. AI can rewrite the words, but operators still share behavior. We score each pair of accounts on:
- **Same reply targets:** replying to the same messages
- **Same timing:** posting or replying to the same thing within 60 seconds
- **Same links and hashtags:** sharing the same URLs, `#hashtags`, `@mentions`, or reposts
- **Same template text:** posting identical text after cleanup (case, links, digits, punctuation, emoji)
- **Same work schedule:** similar weekly activity patterns, like the office hours that exposed Spamouflage

Popular links and tags count less, so only rare shared traces add up. One signal alone can be a coincidence. Several together point to a network.

## It works
On a Telegram dataset of 17.3M comments where 3.1% of active accounts are labeled propaganda accounts, the top 50 groups we found were 52.6% labeled, about 16× the base rate. The top groups also contained unlabeled networks posting template talking points.

## Why it's urgent
Russia's Pravda network published 3.6 million articles in 2024 to seed AI chatbots, which repeated its claims about 33% of the time. Catching coordinated content early helps keep it out of AI systems too.

## Behavior, not opinions
Like Meta's own policy, this tool flags coordinated fake behavior and leaves viewpoints alone.

## Sources
- [OpenAI threat report, Feb 2026](https://openai.com/index/disrupting-malicious-ai-uses)
- [KQED/NPR: OpenAI thwarts Russian and Chinese operations](https://kqed.org/news/11988245/openai-thwarts-influence-operations-by-russia-china-and-israel)
- [SecurityWeek: Meta's Spamouflage takedown](https://www.securityweek.com/meta-fights-sprawling-chinese-spamouflage-operation/amp/)
- [Meta: Q4 2024 Adversarial Threat Report](https://transparency.meta.com/sr/Q4-2024-Adversarial-threat-report)
- [The Hacker News: Romania annuls election](https://thehackernews.com/2024/12/romania-cancels-presidential-election.html)
- [PBS NewsHour: Romania election thrown out](https://www.pbs.org/newshour/show/romania-election-results-thrown-out-after-russian-interference-claims)
- [ScienceBlog: AIPasta study](https://scienceblog.com/neuroedge/?p=225)
- [PADBen: detectors vs. paraphrasing (arXiv)](https://arxiv.org/html/2511.00416v1)
- [United24: Pravda network and AI chatbots](https://united24media.com/war-in-ukraine/researchers-reveal-how-russias-propaganda-network-infects-leading-ai-chatbots-7106)
