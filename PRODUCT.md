# Product

## Register

product

## Platform

web

## Users

General consumers asking factual questions who need answers they can trust. They arrive with a claim or question, want a fast response, and expect to see where the answer came from before they share or act on it. The hackathon demo audience (judges evaluating grounded output) is a secondary audience whose trust hinges on visible citation quality and polish.

## Product Purpose

A live fact-checking chat that verifies claims against the open web in real time. Built for HackwithSeattle 2.0, it combines RocketRide Cloud (production agent pipeline) with Linkup (sourced, cited web search) so every factual answer is traceable to a source URL — not hallucinated from training data.

Success looks like: demo-ready polish, instant-feeling interaction, and clear clickable citations on every verified answer. A later phase will surface richer source context (account names for social posts, stats, diagrams) once verification is established.

## Positioning

The fact-checker that shows its work — every answer linked to live sources you can click and verify yourself.

## Brand Personality

Fast, technical, no-nonsense. Precise like Linear; citation-forward like Perplexity. Confident without being playful or chatbot-cute. The interface should feel like a serious verification tool, not a generic AI companion.

## Anti-references

- Generic ChatGPT-style bubble UI (purple gradients, bland avatars, "helpful assistant" energy)
- Overly playful or cartoonish chatbot aesthetics
- SaaS dashboard clichés (metric cards, eyebrow labels, cream backgrounds)
- Anything that makes verification feel optional or decorative

## Design Principles

1. **Show the proof first.** Citations are not footnotes — they are the product. Every answer should make it obvious where the claim came from and how to verify it.
2. **Speed is trust.** Minimize friction between question and answer. Loading states should feel intentional, not sluggish. The UI should never make users wait without knowing why.
3. **Precision over personality.** Favor clean hierarchy, tight spacing, and readable type over decorative flair. Craft details (micro-interactions, contrast, alignment) earn trust; mascots and gradients erode it.
4. **Demo the pipeline, not the prompt.** The interface should make RocketRide + Linkup grounding visible — users and judges should see that answers come from live web sources, not model memory.
5. **Build for what's next.** Structure the answer area so richer source cards (account names, stats, diagrams) can slot in later without redesigning the whole chat shell.

## Accessibility & Inclusion

Basic accessibility: readable contrast, keyboard-accessible form controls, semantic HTML. No specific WCAG level mandated for the hackathon demo, but avoid contrast failures and ensure reduced-motion-friendly transitions where motion is added.
