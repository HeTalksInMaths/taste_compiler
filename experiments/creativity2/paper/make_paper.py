"""Build an AAAI-style two-column PDF describing the EVO2 experiments.

Plain-language write-up: motivation, methodology, insights, results.
Run: python make_paper.py  ->  evo2_paper.pdf
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, FrameBreak, NextPageTemplate,
    Paragraph, Spacer, Table, TableStyle, Image, KeepTogether,
)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "evo2_paper.pdf")
FIG = os.path.join(HERE, "trajectory.png")

# ── Figure: held-out separation per generation, both arms ─────────────
sonnet_h = [0.059, 0.018, 0.161, 0.121]
haiku_h = [0.059, 0.098, 0.190, 0.068, 0.158, 0.187, 0.169, 0.198]
sonnet_c = [0.212, -0.003, 0.202, 0.202]
haiku_c = [0.212, 0.135, -0.009, 0.135, 0.359, 0.359, 0.359, 0.359]
armc_h = [0.059, 0.277, 0.177, 0.149]
armc_c = [0.212, 0.190, 0.190, 0.396]

plt.figure(figsize=(4.6, 2.9), dpi=200)
plt.axhline(0, color="#999999", lw=0.6)
plt.plot(range(4), sonnet_h, "o-", color="#1a5fb4", lw=1.6, ms=4,
         label="Arm A held-out (larger model)")
plt.plot(range(8), haiku_h, "s-", color="#c01c28", lw=1.6, ms=4,
         label="Arm B held-out (smaller model, 3x volume)")
plt.plot(range(4), armc_h, "^-", color="#613583", lw=1.6, ms=4,
         label="Arm C held-out (smaller model, matched budget)")
plt.plot(range(4), sonnet_c, "o--", color="#1a5fb4", lw=0.9, ms=3, alpha=0.4,
         label="Arm A stationary core")
plt.plot(range(8), haiku_c, "s--", color="#c01c28", lw=0.9, ms=3, alpha=0.4,
         label="Arm B stationary core")
plt.plot(range(4), armc_c, "^--", color="#613583", lw=0.9, ms=3, alpha=0.4,
         label="Arm C stationary core")
plt.xlabel("generation", fontsize=8)
plt.ylabel("separation of best scorer", fontsize=8)
plt.xticks(range(8), fontsize=7)
plt.yticks(fontsize=7)
plt.legend(fontsize=6.2, loc="lower right", framealpha=0.9)
plt.tight_layout()
plt.savefig(FIG)
plt.close()

# ── Figure 2: co-evolution loop diagram ───────────────────────────────
FIG2 = os.path.join(HERE, "coevolution.png")
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig2, ax = plt.subplots(figsize=(4.9, 2.75), dpi=200)
ax.set_xlim(0, 10)
ax.set_ylim(0, 6)
ax.axis("off")

def box(x, y, w, h, text, fc):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12",
                                fc=fc, ec="#333333", lw=0.9))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=6.4)

def arrow(x1, y1, x2, y2, text, tx, ty, style="-|>"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style,
                                 mutation_scale=9, lw=1.0, color="#333333"))
    ax.text(tx, ty, text, ha="center", va="center", fontsize=5.6,
            style="italic", color="#333333")

box(0.3, 3.6, 3.4, 1.9, "GENERATOR\npolicy under RL fine-tuning\nor evolutionary search", "#dbe7f6")
box(6.3, 3.6, 3.4, 1.9, "REWARD\nhardened scorer ensemble\n(+ frozen held-out reward)", "#e4f0dc")
box(6.3, 0.4, 3.4, 1.9, "HACK MINER\njudge labels top-reward\noutputs: genuine or hacked?", "#fdeeda")
box(0.3, 0.4, 3.4, 1.9, "SCORER EVOLUTION\nengineer + four gates\n(+ red-team agents)", "#f6dbdb")
arrow(3.7, 4.55, 6.3, 4.55, "candidate rewrites, scored densely", 5.0, 4.9)
arrow(8.0, 3.6, 8.0, 2.3, "highest-reward samples", 8.05, 2.95, "-|>")
arrow(6.3, 1.35, 3.7, 1.35, "confirmed hacks become\nnew adversarial test pairs", 5.0, 0.85)
arrow(2.0, 2.3, 2.0, 3.6, "updated, re-hardened reward", 1.95, 2.95)
plt.tight_layout()
plt.savefig(FIG2)
plt.close()

# ── Styles (AAAI-like: Times, two columns, 10pt) ──────────────────────
S = {}
S["title"] = ParagraphStyle("title", fontName="Times-Bold", fontSize=15.5,
                            leading=19, alignment=TA_CENTER, spaceAfter=6)
S["author"] = ParagraphStyle("author", fontName="Times-Roman", fontSize=10.5,
                             leading=13, alignment=TA_CENTER, spaceAfter=14)
S["h1"] = ParagraphStyle("h1", fontName="Times-Bold", fontSize=11.5,
                         leading=14, spaceBefore=9, spaceAfter=4)
S["h2"] = ParagraphStyle("h2", fontName="Times-Bold", fontSize=10,
                         leading=12.5, spaceBefore=6, spaceAfter=3)
S["body"] = ParagraphStyle("body", fontName="Times-Roman", fontSize=9.6,
                           leading=11.8, alignment=TA_JUSTIFY, spaceAfter=4,
                           firstLineIndent=10)
S["bodyni"] = ParagraphStyle("bodyni", parent=S["body"], firstLineIndent=0)
S["abstract"] = ParagraphStyle("abstract", fontName="Times-Roman", fontSize=9.2,
                               leading=11.2, alignment=TA_JUSTIFY,
                               leftIndent=10, rightIndent=10, spaceAfter=6)
S["abshead"] = ParagraphStyle("abshead", fontName="Times-Bold", fontSize=10.5,
                              leading=12, alignment=TA_CENTER, spaceAfter=3)
S["caption"] = ParagraphStyle("caption", fontName="Times-Roman", fontSize=8.4,
                              leading=10, alignment=TA_JUSTIFY, spaceBefore=3,
                              spaceAfter=6)
S["ref"] = ParagraphStyle("ref", fontName="Times-Roman", fontSize=8.6,
                          leading=10.4, alignment=TA_JUSTIFY, spaceAfter=2,
                          leftIndent=12, firstLineIndent=-12)

TSTYLE = TableStyle([
    ("FONTNAME", (0, 0), (-1, -1), "Times-Roman"),
    ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 8),
    ("LEADING", (0, 0), (-1, -1), 9.6),
    ("LINEABOVE", (0, 0), (-1, 0), 0.8, colors.black),
    ("LINEBELOW", (0, 0), (-1, 0), 0.4, colors.black),
    ("LINEBELOW", (0, -1), (-1, -1), 0.8, colors.black),
    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ("TOPPADDING", (0, 0), (-1, -1), 1.5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
])


def P(text, style="body"):
    return Paragraph(text, S[style])


story = []

# ── Title block ────────────────────────────────────────────────────────
story.append(P("Selection Beats Sophistication: Discovering Interpretable "
               "Creativity Metrics with Adversarial Agent Evolution", "title"))
story.append(P("Anonymous Submission", "author"))
story.append(P("Abstract", "abshead"))
story.append(P(
    "Judging whether one piece of writing is more <i>creative</i> than another is easy "
    "for people and hard to automate transparently. We ask whether language-model agents can "
    "<b>discover</b> short, deterministic, fully inspectable Python scoring functions that rank "
    "a fresher rewrite above a flatter one. Our system pits an <i>engineer</i> agent (writes "
    "scorers from failure analyses) against an <i>adversary</i> agent (writes test cases that "
    "decouple the champion's signal from real creativity), with a deterministic referee "
    "enforcing four gates: validity, anti-memorization, behavioral novelty, and usefulness. "
    "Across three arms — a larger model, a smaller model at triple volume, and the smaller "
    "model at the larger's exact budget — final champions are statistically indistinguishable "
    "on a frozen 26-case core (overlapping bootstrap CIs), and all three converge on "
    "conjunctive novelty-times-sanity-gate designs. A 12,000-program ablation shows this "
    "two-factor shape is NOT favored by static fitness (1.07x enrichment): it is selected by "
    "<b>adversarial survival</b> — every single-signal champion was destroyed within one "
    "generation of taking the lead. We then invert the pipeline: a blind compositional search "
    "over agent-built primitives, with the same gates but no theory-first prior, discovers a "
    "non-intuitive scorer — <i>creative edits are few and placed where the text's information "
    "concentrates</i> — that is behaviorally decorrelated from every incumbent (max |r|=0.23), "
    "passes a falsifiable explanation gate (12/12 predictions, including designed "
    "falsification bait), and transfers to acclaimed human writing where every evolved "
    "champion fails (5/6 vs 0/6). Three independent blind judge agents reproduce 91% of the "
    "test labels unanimously. We conclude that selection pressure and honest evaluation "
    "machinery, not proposer sophistication, drive metric discovery — and that freeing the "
    "hypothesis space matters more than strengthening the proposer.",
    "abstract"))
story.append(FrameBreak())

# ── 1 Introduction ─────────────────────────────────────────────────────
story.append(P("1&nbsp;&nbsp;Introduction", "h1"))
story.append(P(
    "Suppose an editor rewrites the sentence <i>“The storm arrived late at night”</i> as "
    "<i>“Night cracked open into a storm.”</i> Most readers agree the second is more creative. "
    "Now suppose we want a program to make that call — millions of times, cheaply, and in a "
    "way we can audit. This is the problem of <b>scoring subjective text quality</b>, and "
    "creativity is among its hardest instances.", "bodyni"))
story.append(P(
    "The fashionable answer is to ask a large language model (LLM) to be the judge. That "
    "works, but the judge is a black box: we cannot inspect <i>why</i> it preferred one text, "
    "we cannot run it offline in microseconds, and its preferences drift with the model "
    "version. The classical answer is to hand-craft a metric — count rare words, count "
    "clichés — but hand-crafted metrics encode their author's blind spots and, as we show, "
    "collapse the moment a test case decouples the proxy from the quality it stands for."))
story.append(P(
    "This paper explores a third path: let LLM agents <b>write the metric as code</b>, and "
    "let an evolutionary process — selection on measured performance, plus an adversary that "
    "continually manufactures harder test cases — decide what survives. The output is not a "
    "neural network but a short, deterministic Python function anyone can read. Two "
    "questions drive the work:"))
story.append(P(
    "<b>Q1.</b> Can such a loop <i>discover</i> a genuinely novel, robust scoring principle, "
    "rather than just re-tuning known ones?", "bodyni"))
story.append(P(
    "<b>Q2.</b> When it succeeds, what deserves the credit — the intelligence of the model "
    "writing the proposals, or the evolutionary scaffolding around it? We test this with "
    "three arms: a larger model, a smaller model at triple volume, and — to break the "
    "volume/size confound — the smaller model at the larger model's exact budget.", "bodyni"))
story.append(P(
    "<b>Q3.</b> Can the pipeline surface a scorer that is <i>non-intuitive</i> — one no "
    "theory-guided proposer would write — while remaining rigorously explainable? We test "
    "this by inverting the pipeline: a blind compositional search over agent-built "
    "primitives, judged by the same gates, followed by an explanation gate that accepts an "
    "interpretation only if its predictions survive designed falsification.", "bodyni"))
story.append(P(
    "Our answers: yes to Q1 — with an important qualification our own ablation forced "
    "(Sec. 5.1); decisively yes to Q2 — acceptance rates were identical across model tiers, "
    "the matched-budget arm is statistically indistinguishable from the larger model's arm, "
    "and all three arms converged on the same design shape; and yes to Q3 — the blind "
    "search discovered a scorer no agent proposed in nine theory-first generations, whose "
    "validated interpretation is that <i>creative edits are few and placed where the "
    "text's information concentrates</i>."))

# ── 2 The task in plain terms ─────────────────────────────────────────
story.append(P("2&nbsp;&nbsp;The Task, in Plain Terms", "h1"))
story.append(P(
    "<b>What a scorer is.</b> A scorer is a Python function <font face='Courier' size='8'>"
    "score(text, original)</font> returning a number between 0 and 1. It sees a rewrite and "
    "the original it came from, and should give higher numbers to rewrites that are more "
    "creative. It must be deterministic (same input, same output), must not call any "
    "network or model, and may use only ordinary computation plus one public resource: a "
    "table of how frequent each English word is in large text corpora.", "bodyni"))
story.append(P(
    "<b>What a test case is.</b> Each test case is a triple: an original two-sentence "
    "passage, a rewrite that a careful human would call <i>more</i> creative, and a rewrite "
    "they would call <i>less</i> creative — all describing the same facts. A scorer handles "
    "the case correctly if it gives the more creative version the higher score."))
story.append(P(
    "<b>How we measure success.</b> Accuracy (fraction of cases ranked correctly) hides too "
    "much: a scorer that squeaks past by 0.001 on every case looks identical to one that "
    "separates confidently. We therefore score both versions of every case individually and "
    "use the <b>separation</b>: the average score of all the better rewrites minus the "
    "average score of all the worse ones. A separation of 0 means the scorer cannot tell "
    "them apart at all; 1 is a perfect, maximally confident split. We report accuracy and "
    "the two averages alongside it, so over- and under-confidence are both visible."))
story.append(P(
    "<b>Why normalization matters.</b> Every scorer must map to the same 0–1 scale, but "
    "calibrating that scale on the test cases themselves would be cheating. Scorers instead "
    "calibrate against fixed reference statistics computed once from the public word-"
    "frequency table (for example, how surprising the average English word is), so the "
    "scale is anchored to the language, not to our data."))

# ── 3 Method ───────────────────────────────────────────────────────────
story.append(P("3&nbsp;&nbsp;Method: an Adversarial Evolutionary Loop", "h1"))
story.append(P(
    "The system has one deterministic referee (ordinary code, no model) and two agent "
    "roles, each played by an LLM with its own private context.", "bodyni"))
story.append(P(
    "<b>The engineer</b> proposes new scorers. Each generation it receives: a map of "
    "creativity concepts distilled from the research literature (which concepts existing "
    "scorers already measure and which are unclaimed), a statistics table for every current "
    "scorer, a similarity matrix showing which scorers behave alike, the champion's code, "
    "and the specific training cases the champion gets wrong. It must write complete, "
    "runnable modules — reasoning first, code second."))
story.append(P(
    "<b>The adversary</b> proposes new test cases. It sees only the champion's code and a "
    "list of attack angles already used, and must invent a <i>new</i> way to decouple the "
    "champion's signal from real creativity — for example, if the champion rewards rare "
    "words, write flat rewrites full of stiff formal vocabulary (high signal, no creativity) "
    "and brilliant rewrites made of everyday words (low signal, high creativity). Candidate "
    "cases are kept only if the champion actually struggles on them; most join the training "
    "set and a fixed share is diverted, sight unseen, into a held-out set."))
story.append(P(
    "<b>Four acceptance gates.</b> Every proposed scorer passes through automatic checks "
    "before it may join the population:"))
story.append(P(
    "1.&nbsp;<b>Validity</b> — it runs without error, stays within 0–1, is deterministic, "
    "and is not near-constant.", "bodyni"))
story.append(P(
    "2.&nbsp;<b>No memorization</b> — the referee parses the code and inspects every "
    "hard-coded word list; if it contains rare words copied from the visible test cases, "
    "or any large content word list at all, the scorer is rejected. (This gate exists "
    "because, in a pilot, an agent shown failing cases quietly copied eleven of their "
    "distinctive verbs into its feature list, inflating its measured skill.)", "bodyni"))
story.append(P(
    "3.&nbsp;<b>Behavioral novelty</b> — we record, for every scorer, its per-case "
    "score difference between the better and worse rewrite. If a new proposal's pattern of "
    "differences correlates above 0.6 with any existing scorer's, it is the same signal in "
    "new clothes and earns no novelty credit, no matter how different its stated mechanism "
    "sounds.", "bodyni"))
story.append(P(
    "4.&nbsp;<b>Usefulness</b> — it must beat the population's median separation, or be "
    "genuinely novel with positive separation.", "bodyni"))
story.append(P(
    "<b>Three tiers of test data keep everyone honest.</b> The <i>training</i> cases are "
    "visible to agents and drive selection. The <i>held-out</i> cases are never shown to any "
    "agent and exist only so we can check whether a champion's skill is real. The "
    "<i>stationary core</i> is a small, never-growing subset of the original cases, giving "
    "one number that stays comparable across all generations even as the test set grows "
    "harder."))
story.append(P(
    "<b>Gate costs, measured.</b> The gates act on behavior, not ideas, but two have "
    "measurable creativity costs we quantify in Sec. 5: the usefulness gate can kill "
    "weak-born embodiments of good ideas (a rejected proposal's mechanism family later "
    "produced our best discovery), and novelty-by-correlation inherits the eval's "
    "narrowness. Our mitigations — a probation nursery and quality-diversity niching — are "
    "specified in the discussion; threshold sensitivity is reported in Sec. 5.5.", "bodyni"))
story.append(P(
    "<b>A second discovery mode: blind search + explanation gate.</b> The engineer is "
    "theory-first by construction — we require a named mechanism up front, which biases "
    "proposals toward the textbook. To search beyond intuition we add an inverted mode: "
    "(1) distill a typed primitive library from everything the agents built (per-token "
    "corpus-surprisal series, edit-alignment opcodes from sequence matching, frequency "
    "bands, position and sentence structure); (2) run a seeded genetic-programming search "
    "over tens of thousands of compositions — no theory, no LLM in the loop; (3) apply the "
    "SAME four gates, with behavioral decorrelation now a hard requirement; (4) hand "
    "survivors to an interpreter agent that must state what the program measures and stake "
    "three falsifiable predictions, tested on fresh probe pairs it writes — half designed "
    "to falsify its own reading. A discovery is accepted as explainable only if the "
    "predictions hold.", "bodyni"))
story.append(P(
    "<b>Schedule.</b> The population holds at most ten scorers: the six fittest, up to two "
    "protected slots for the most behaviorally unusual, and the newest arrivals. Each "
    "generation adds a batch of engineer proposals and adversary cases; the loop stops when "
    "two consecutive generations bring neither a better champion nor an accepted novel "
    "scorer. The initial population is four baseline scorers implementing standard ideas "
    "from the creativity literature: word rarity, unusual word combinations, an "
    "“is this overdone?” sanity check, and their product."))

# ── 4 Experiments ─────────────────────────────────────────────────────
story.append(P("4&nbsp;&nbsp;Experiments", "h1"))
story.append(P(
    "<b>Arm A (larger model, low volume).</b> A mid-size commercial LLM played both roles "
    "for three generations: 3 scorer proposals and 8 adversarial candidates per generation "
    "(6 kept).", "bodyni"))
story.append(P(
    "<b>Arm B (smaller model, high volume).</b> A much smaller, cheaper LLM played both "
    "roles under an identical harness, seeds, and gates, but at three times the mutation "
    "volume — 9 proposals per generation from three parallel engineers with different "
    "briefs, and 16 adversarial candidates (10 kept) from two parallel adversaries — and "
    "ran for seven agent generations. Everything else was held fixed."))
story.append(P(
    "<b>Arm C (smaller model, matched budget).</b> The smaller model at Arm A's exact "
    "protocol — 3 proposals and 6 kept cases per generation, 3 generations — isolating "
    "model tier with volume and generations controlled.", "bodyni"))
story.append(P(
    "<b>Blind search.</b> 20,000 random compositions plus four GP refinement rounds over "
    "the primitive library, then the decorrelation filter (|r| < 0.5 against every "
    "incumbent fingerprint) and the explanation gate.", "bodyni"))
story.append(P(
    "All arms start from the same 42 test cases (20 built from real internet text plus 22 "
    "from two earlier adversarial rounds), split deterministically into 29 training and 13 "
    "held-out cases. The stationary core is later expanded to 26 with fresh internet-"
    "grounded cases built blind to all scorers and never used in training."))

# Table 1: trajectories
t1 = Table([
    ["", "gen", "train", "champion (best scorer)", "sep.", "held-out", "core"],
    ["A", "0", "29", "unusual-combination baseline", "0.072", "0.059", "0.212"],
    ["A", "1", "33", "added-detail structure (agent)", "0.032", "0.018", "−0.003"],
    ["A", "2", "37", "kept-skeleton + fresh insert (agent)", "0.129", "0.161", "0.202"],
    ["A", "3", "41", "(same champion holds)", "0.074", "0.121", "0.202"],
    ["B", "0", "29", "unusual-combination baseline", "0.072", "0.059", "0.212"],
    ["B", "1", "36", "insert-vs-swap structure (agent)", "0.074", "0.098", "0.135"],
    ["B", "2", "43", "short-word concreteness (agent)", "0.201", "0.190", "−0.009"],
    ["B", "3", "50", "(reverts to gen-1 champion)", "0.055", "0.068", "0.135"],
    ["B", "4", "57", "variety × rarity gate (agent)", "0.106", "0.158", "0.359"],
    ["B", "5", "63", "(same champion holds)", "0.139", "0.187", "0.359"],
    ["B", "6", "70", "(same champion holds)", "0.123", "0.169", "0.359"],
    ["B", "7", "77", "(same champion holds)", "0.154", "0.198", "0.359"],
    ["C", "0", "29", "unusual-combination baseline", "0.072", "0.059", "0.212"],
    ["C", "1", "33", "topic coherence (agent)", "0.166", "0.277", "0.190"],
    ["C", "2", "37", "(same champion, post-attack)", "0.080", "0.177", "0.190"],
    ["C", "3", "41", "novelty x rarity gate (agent)", "0.089", "0.149", "0.396"],
], colWidths=[0.15 * inch, 0.23 * inch, 0.32 * inch, 1.42 * inch, 0.35 * inch, 0.45 * inch, 0.34 * inch])
t1.setStyle(TSTYLE)
story.append(KeepTogether([
    t1,
    P("<b>Table 1:</b> Champion trajectories in all three arms. “sep.” is separation on "
      "the (growing) training set; “held-out” is separation on cases no agent ever "
      "saw; “core” is the never-growing stationary subset. Agent-written champions "
      "displaced the baselines in both arms.", "caption")]))

story.append(Image(FIG, width=3.15 * inch, height=1.98 * inch))
story.append(P(
    "<b>Figure 1:</b> Held-out separation (solid) and stationary-core separation (dashed) of "
    "each generation's champion. Arm B is chaotic early — including a generation-2 champion "
    "whose core score went <i>negative</i> (overfit to the adversarial distribution) — then "
    "converges. Arm C (matched budget) reproduces the same dynamics at one third the volume: "
    "an immediate agent champion, an adversarial setback, and a conjunctive final winner "
    "with the highest single-arm core score.", "caption"))

# ── 5 Results ─────────────────────────────────────────────────────────
story.append(P("5&nbsp;&nbsp;Results", "h1"))
story.append(P("5.1&nbsp;&nbsp;A Classical Principle — Selected by Attack, Not by Fitness", "h2"))
story.append(P(
    "Creativity research holds that creativity is not novelty alone: an idea must be both "
    "<i>new</i> and <i>fitting</i> (Runco and Jaeger 2012), with preference peaking at "
    "moderate novelty (Berlyne 1971). In ALL THREE arms every surviving champion has the "
    "same architecture — a novelty signal <b>multiplied by a sanity gate</b>: Arm A scores "
    "insertion novelty <i>given</i> a preserved skeleton; Arm B scores structural variety "
    "<i>given</i> content rarity; Arm C scores novelty <i>given</i> rarity-coherence. "
    "Single-signal champions (rarity, divergence, concreteness) were each destroyed by an "
    "adversarial round within one generation of taking the lead.", "bodyni"))
story.append(P(
    "An early draft claimed this structure “emerged unseeded.” A reviewer correctly "
    "objected that one baseline was itself a product, so we ran the ablation: among 12,000 "
    "random compositions with no seeds and no LLM, multiplicative/gated shapes show NO "
    "enrichment among the top 5% of separators (1.07x; ratio 1.01x). The honest claim is "
    "therefore sharper than the original: <b>two-factor structure is not favored by static "
    "fitness; it is selected by adversarial survival.</b> On a fixed test set, a "
    "single-signal scorer can score as well as a gated one — but only the gated ones "
    "survive rounds of attack, because a conjunction forces an attacker to defeat every "
    "factor at once. The classical definition re-emerges not as a property of what "
    "creativity looks like on average, but of what survives attempts to fake it — arguably "
    "closer to why the two-factor definition exists in the first place.", "bodyni"))

story.append(P("5.2&nbsp;&nbsp;Model Quality Sets the Pace, Not the Destination", "h2"))
t2 = Table([
    ["", "Arm A", "Arm B", "Arm C"],
    ["model tier", "larger", "smaller", "smaller"],
    ["budget (props x gens)", "3 x 3", "9 x 7", "3 x 3"],
    ["accepted / proposed", "3/9", "~15/45", "4/9"],
    ["champion turnovers", "2", "4", "2"],
    ["final champion form", "conjunctive", "conjunctive", "conjunctive"],
    ["26-core accuracy", "0.92", "1.00", "0.85"],
    ["26-core separation", "0.222", "0.241", "0.300"],
    ["95% CI", "[.15,.29]", "[.19,.30]", "[.20,.40]"],
], colWidths=[1.28 * inch, 0.66 * inch, 0.66 * inch, 0.66 * inch])
t2.setStyle(TSTYLE)
story.append(KeepTogether([
    t2,
    P("<b>Table 2:</b> Three-arm comparison on the expanded 26-case stationary core "
      "(6 original + 20 fresh internet-grounded cases, built blind to all scorers, never "
      "used in training or selection; bootstrap CIs, 10k resamples). All intervals "
      "overlap: no model-size effect is detectable with volume and generations controlled.", "caption")]))
story.append(P(
    "Three observations answer Q2, now with the volume/size confound removed by Arm C.", "bodyni"))
story.append(P(
    "<b>(a) The gates, not the proposer, set the quality bar.</b> The acceptance rate was "
    "33% under both models. The smaller model produced four times as many "
    "“copycats” — proposals whose stated mechanism sounded new but whose behavior "
    "correlated up to 0.94 with an existing scorer — and the behavioral-novelty gate caught "
    "every one. Claimed mechanisms do not survive contact with measured behavior."))
story.append(P(
    "<b>(b) Attacking is easier than building.</b> The smaller model's adversaries matched "
    "and then exceeded the larger model's: one of its rounds achieved the worst possible "
    "margin on all ten kept cases, the hardest single hit in either arm. Finding a scorer's "
    "blind spot appears to demand less capability than designing a scorer."))
story.append(P(
    "<b>(c) With budget matched, the model-size effect vanishes.</b> Arm C — the smaller "
    "model at the larger model's exact protocol — dethroned the seed champion in one "
    "generation, weathered an adversarial setback, and finished with a conjunctive champion "
    "whose 26-core CI [0.195, 0.402] overlaps both other arms (Table 2). Volume helps the "
    "smaller model explore more (Arm B tried five times the proposals), but it is not "
    "necessary for parity: the selection loop, not scale or volume, is the operative "
    "ingredient. Acceptance rates were 33%, 33%, and 44% across arms — the gates, not the "
    "proposer, set the bar everywhere."))

story.append(P("5.3&nbsp;&nbsp;What the Honesty Machinery Caught", "h2"))
story.append(P(
    "The run is as interesting for what the referee <i>rejected</i> as for what it kept.", "bodyni"))
story.append(P(
    "<b>A memorizing scorer.</b> In the pilot that motivated gate 2, an agent shown the "
    "champion's failures copied their distinctive vocabulary into its own word lists; its "
    "measured skill was partly a lookup table of the test set. The automated code-inspection "
    "gate now rejects this pattern outright."))
story.append(P(
    "<b>A distribution-overfit champion.</b> Arm B's generation-2 leader posted the best "
    "training separation seen to that point (0.201) while scoring <i>below zero</i> on the "
    "stationary core: it separated the adversary-authored cases while failing ordinary "
    "prose. Without a never-growing tier, this would have read as a breakthrough."))
story.append(P(
    "<b>A test-growth rule that backfired.</b> Our rule kept the ten candidate cases the "
    "champion handled <i>worst</i>. Once the champion became strong enough that every attack "
    "failed, “worst” cases were still ranked correctly — so the test set began "
    "absorbing champion-friendly cases and the champion's measured skill inflated. An "
    "adversarial test set only stays hard while the adversary stays competitive; the keep-"
    "rule must require the champion to actually fail, or discard the batch."))

story.append(P(
    "Two further checks respond to methodological concerns. <b>Threshold sensitivity:</b> "
    "the reported discovery archive is identical for novelty cutoffs 0.5–0.8 (and loses two "
    "members at 0.4) — the 0.6 setting does no hidden work. <b>Distributional leakage:</b> "
    "correlating each champion's per-case held-out margin with that case's lexical overlap "
    "against the training text (overlap range 0.29–0.79) yields |r| ≤ 0.15 for every "
    "scorer — no evidence that performance rides on shared vocabulary.", "bodyni"))

story.append(P("5.4&nbsp;&nbsp;A Non-Intuitive Scorer, Discovered Blind and Validated", "h2"))
story.append(P(
    "Nine theory-first generations produced strong but recognizable ideas — every accepted "
    "scorer's mechanism can be found in a linguistics or creativity textbook. To search "
    "beyond intuition we ran the blind mode: 20,000 machine-generated compositions of "
    "agent-built primitives, judged by the same four gates with decorrelation as a hard "
    "requirement, then the explanation gate. Six programs survived. The strongest — we will "
    "call it the <b>edit-placement scorer</b> — combines two statistics that no one had "
    "thought to put together: the sparsity of the edit set (how few changes the rewrite "
    "makes), and the mismatch between two concentration profiles — where in the text the "
    "changes sit, versus where in the text the information sits (word-by-word "
    "surprisingness, from public corpus frequencies). In one line: "
    "<i>score = edit sparsity − |concentration of changes − concentration of "
    "information|</i>.", "bodyni"))
story.append(P(
    "Its validated reading: <b>prefer rewrites that make FEW changes, placed where the "
    "text's information lives.</b> A skilled edit does not scatter novelty everywhere; it "
    "spends one or two changes exactly where the passage carries its meaning. No agent, no "
    "hand-coder, and no earlier phase of this project proposed measuring the alignment of "
    "those two profiles.", "bodyni"))
story.append(P(
    "We defend its novelty and explainability on five grounds. <b>(1) Behavioral:</b> its "
    "per-case fingerprint correlates at most 0.23 with every incumbent — the most "
    "decorrelated scorer in the project, robust to the novelty threshold (identical from "
    "0.5 to 0.8). <b>(2) Mechanistic:</b> across ~60 agent proposals in three arms, nothing "
    "measured profile alignment; the nearest relative (an edit-locality idea) was rejected "
    "three generations earlier as a weak embodiment — the agents circled the concept but "
    "never landed it. <b>(3) Explainable with predictive force:</b> an independent "
    "interpreter agent derived its mechanics, staked three falsifiable predictions, and "
    "wrote twelve fresh probe cases — six designed to falsify its own reading. All 12/12 "
    "held on independent verification. <b>(4) External transfer:</b> on six acclaimed "
    "human lyric lines (Cohen, Dylan, Radiohead, Mitchell, Waits) versus flattened "
    "paraphrases — critical consensus, not LLM labels — the edit-placement scorer picks the masterwork 5/6 while "
    "BOTH evolved champions score 0/6; it also agrees best with the independent judge "
    "majority (0.70 vs the champion's 0.61). <b>(5) Reproducible family:</b> a seed-repeat "
    "of the search finds different programs from the same family — concentration "
    "statistics composed with anchor-relative ratios — including another perfect-core "
    "variant.", "bodyni"))
story.append(P(
    "Explainability here includes knowing when it fails: the validated interpretation "
    "exposes that the edit-placement scorer is blind to edits made of grammatical filler words (a rhetorical repetition device "
    "collapses its score) and that a bland inserted adjective can outrank two genuine "
    "replacements. These are documented, testable failure modes — the difference between "
    "an interpretable metric and a plausible-sounding one.", "bodyni"))
story.append(P(
    "The methodological point generalizes: the binding constraint on discovering "
    "non-intuitive metrics was never the acceptance gates — it was the theory-first "
    "proposal prior. Removing the prior while KEEPING the gates is what produced a "
    "discovery that is both unfamiliar and trustworthy; the gates are precisely what let "
    "us trust a scorer from a search space nobody curated.", "bodyni"))

story.append(P("5.5&nbsp;&nbsp;Label Validity: an Independent Judge Panel", "h2"))
story.append(P(
    "The reviewer's central concern is that test labels are LLM-authored. As a first "
    "validation step (human ratings are in progress), three independently prompted blind "
    "raters — a freshness rubric, an editor rubric, and a reader rubric, spanning two model "
    "tiers — judged all 33 held-out cases with randomized A/B order and no provenance. "
    "They were unanimous with one another on 33/33 cases and reproduced 30/33 (91%) of the "
    "labels; the three unanimous disagreements are best read as label errors and flagged "
    "for correction. We state the caveat plainly: unanimity among model raters can reflect "
    "shared bias, so this validates label consistency across independent model raters, not "
    "human ground truth. A label-free check is possible too: agreement with the judge "
    "majority ranks the edit-placement scorer first (0.70), ahead of every evolved champion.", "bodyni"))

story.append(P("5.6&nbsp;&nbsp;The Ceiling", "h2"))
story.append(P(
    "The loop eventually converged by <i>adversary exhaustion</i>: in Arm B's final "
    "generation, neither of two fresh attack angles produced a single case the champion "
    "mis-ranked, and the engineers' remaining textbook ideas (a standard lexical-diversity "
    "algorithm, a statistical de-confounding trick, two-word-sequence surprise) each failed "
    "the gates on the merits. The concepts that stayed unmeasured — whether an inserted "
    "image actually <i>fits</i> its context, true meaning-level distance — are exactly the "
    "ones that word-frequency statistics cannot express. One adversary demonstrated this "
    "pointedly, submitting pairs whose two rewrites are statistically near-identical but "
    "semantically opposed (an apt image versus a subtly impossible one). No scorer in the "
    "population can tell such pairs apart, and on the evidence here, none built from "
    "frequency statistics ever will. That boundary — freshness is measurable, fit is not — "
    "is, we think, the clearest empirical statement of where interpretable text metrics end "
    "and meaning-aware models must begin.", "bodyni"))

# ── 6 Research agenda ─────────────────────────────────────────────────
story.append(P("6&nbsp;&nbsp;From Measuring Creativity to Improving It: "
               "a Research Agenda", "h1"))
story.append(P(
    "So far the scorers have been judges. But a function that runs in microseconds and "
    "can be read line-by-line unlocks four distinct uses: an <b>evaluation and comparison "
    "tool</b> (A/B tests between models or prompts, regression tests when a system "
    "changes, leaderboards that anyone can audit); a <b>fitness function</b> for "
    "evolutionary search over generating programs or prompts, where its determinism and "
    "speed matter most; a <b>reward</b> for reinforcement-learning fine-tuning (RLFT) of a "
    "generator; and a <b>scientific instrument</b> that turns a vague quality into "
    "falsifiable hypotheses. Seen from the training angle, everything we learned about how "
    "scorers fail is a lesson about how rewards get <b>hacked</b>, learned cheaply before "
    "any expensive run. This section states the general recipe, then turns each empirical "
    "lesson into a concrete proposal.", "bodyni"))

story.append(P("6.1&nbsp;&nbsp;The Recipe Is Not About Creativity", "h2"))
story.append(P(
    "Nothing in the pipeline is specific to creativity except its content. The full "
    "recipe, stated generally, is: <b>(1)</b> research agents read the literature on the "
    "target quality and distill it into a causal map — what the quality rewards, what it "
    "punishes, and what it requires (for creativity: novelty, moderated by fit; for other "
    "qualities, other structures); <b>(2)</b> measurement agents ground each node of that "
    "map in computable signals from real reference data, honestly recording which nodes "
    "the available resources can and cannot reach; <b>(3)</b> the adversarial loop of this "
    "paper — proposer, attacker, and referee with honesty gates — evolves interpretable "
    "scorers against a test set that grows wherever the current best scorer is blind; and "
    "<b>(4)</b> when theory-guided proposing plateaus, a blind compositional search over "
    "the accumulated primitives, judged by the same gates plus a falsification-tested "
    "explanation step, extends the search beyond what anyone would think to write.", "bodyni"))
story.append(P(
    "Any hard-to-measure abstract quality fits this template — trustworthiness of a "
    "product description, persuasiveness of an argument, tactfulness of a refusal, "
    "pedagogical clarity, adherence to a house style — provided two things exist: paired "
    "comparisons that manipulate the quality while holding content fixed, and measurement "
    "primitives at the right rung of the resource ladder. The claim is not speculative: "
    "the same engine, earlier in this research program, evolved scorers for the "
    "persuasiveness of marketing copy and for a distinctive songwriting style, and "
    "exhibited the same dynamics reported here — single-signal champions destroyed by "
    "targeted counterexamples, conjunctive designs surviving. The pipeline is a general "
    "procedure for converting a folk concept into a hardened, auditable measurement — and "
    "then using that measurement to drive models toward the concept.", "bodyni"))

story.append(P("6.2&nbsp;&nbsp;Harden the Reward Before Training, Not During", "h2"))
story.append(P(
    "A policy trained to maximize a naive creativity reward will discover, within hours, "
    "exactly the exploits our adversary found in minutes: flood a rarity reward with ornate "
    "vocabulary (our purple-prose attack), flood a change-based reward with meaning-"
    "preserving shuffles (synonym churn), flood an elaboration reward with empty "
    "qualifiers (padding). Each adversarial axis in our runs is a <i>preview of a reward-"
    "hacking failure mode</i>, obtained at the cost of a few agent calls rather than a "
    "training run. We therefore propose treating our loop as a standard <b>pre-flight "
    "procedure for reward functions</b>: before optimizing against any subjective-quality "
    "reward, run agent red teams against it and report its <b>decouplability</b> — how "
    "easily an attacker produces high-reward, low-quality text — with the same rigor as "
    "its agreement with human judgment. Our margin statistics give decouplability a "
    "number.", "bodyni"))
story.append(P(
    "The runs also say <i>which reward shapes survive</i>. Additive rewards are decouplable "
    "by maximizing their strongest term. Multiplicative, gated rewards force an attacker to "
    "satisfy every factor simultaneously — which is precisely why both arms converged on "
    "products. Two structural rules follow for creativity rewards: <b>(i)</b> compose them "
    "as a novelty term times one or more sanity gates (appropriateness, coherence), never "
    "as a weighted sum; <b>(ii)</b> shape the novelty term as an inverted U — reward "
    "<i>moderate</i> novelty relative to the source and penalize overshoot — so that "
    "“more is always better” never holds along any single axis. The century-old "
    "observation that people prefer moderate novelty (Berlyne 1971) here becomes a "
    "practical reward-shaping principle: the peak of the U is exactly where a reward "
    "stops being gameable by exaggeration."))

story.append(P("6.3&nbsp;&nbsp;Reward the Edit, Not the Text", "h2"))
story.append(P(
    "The single most portable design element our loop discovered is <b>relational "
    "scoring</b>: every strong scorer measured the rewrite <i>against its own source</i> — "
    "what was kept, what was inserted, how far the change went — rather than measuring the "
    "text in isolation. For RLFT this matters twice. First, an anchor-relative reward "
    "cannot be satisfied by collapsing to one high-scoring house style, because each prompt "
    "carries its own baseline and reward is only available by improving <i>this</i> text; "
    "style collapse is the classic failure of absolute style rewards. Second, distribution-"
    "level separation gives <i>dense</i> credit: a policy earns partial reward for partial "
    "improvement, where accuracy-style rewards are all-or-nothing.", "bodyni"))
story.append(P(
    "Two refinements from late generations are directly usable as training objectives. "
    "<b>Novelty-per-edit</b> — dividing novelty gained by the size of the edit — makes one "
    "perfect inserted image outrank a wholesale rewrite, encoding an editor's economy as "
    "an optimizable quantity. And <b>concentration of change</b> — whether the novelty is "
    "localized in one or two spans or smeared across the text — distinguishes a landed "
    "image from churn using only alignment statistics. Both are cheap, deterministic, and "
    "were invented by the agents under adversarial pressure."))
story.append(P(
    "Finally, our ceiling result dictates a <b>two-tier reward</b>: the deterministic "
    "scorer as the dense, every-sample signal, and an expensive meaning-aware check "
    "(embedding similarity, an LLM judge, or a human) applied <i>sparsely</i>, only to "
    "candidates the cheap tier already rates highly. The boundary we located — word "
    "statistics certify freshness but cannot certify fit — is exactly the boundary where "
    "the budget should shift tiers."))

story.append(P("6.4&nbsp;&nbsp;Close the Loop: the Generator Is the Strongest "
               "Red Team", "h2"))
story.append(P(
    "Our adversary writes attacks by reasoning about the champion's code. A policy under "
    "optimization does something stronger: it <i>searches</i> the reward landscape directly "
    "and finds exploits no reasoner anticipates. The natural next system therefore closes "
    "the loop (Figure 2): train or evolve a generator against the current hardened scorer "
    "ensemble; mine its highest-reward outputs; have a judge (human or meaning-aware model) "
    "label which are genuinely creative and which merely score well; and feed the "
    "high-reward-but-hollow ones back as new adversarial test cases — the best test cases "
    "obtainable, because they are the reward's <i>actual</i> failure modes. The scorer side "
    "then evolves as in this paper, and the improved reward retrains the generator. This is "
    "generative-adversarial in spirit, with two differences that matter for science: the "
    "discriminator stays <i>interpretable</i> (its updates are code diffs with named "
    "mechanisms, not weight updates), and every escalation leaves an audit trail.", "bodyni"))
story.append(Image(FIG2, width=3.15 * inch, height=1.77 * inch))
story.append(P(
    "<b>Figure 2:</b> The proposed co-evolution loop. The right half is standard reward-"
    "driven generation; the left half is this paper's scorer-evolution harness. The "
    "generator's own high-reward failures become the adversarial test cases that re-harden "
    "the reward.", "caption"))
story.append(P(
    "Our failure catalog supplies the guardrails this loop needs. Keep a <b>frozen "
    "held-out reward</b> — an ensemble never used during training — and monitor the gap "
    "between training reward and held-out reward as a live hacking meter (our stationary "
    "core, generalized). Require kept test cases to actually <i>defeat</i> the current "
    "reward, or the eval dilutes and measured skill inflates (our backfired keep-rule). "
    "And keep the reward ensemble behaviorally diverse using fingerprint decorrelation, so "
    "the policy cannot satisfy a single signal family and call it creativity."))

story.append(P("6.5&nbsp;&nbsp;What a Scorer Can Teach Us About Creativity "
               "Itself", "h2"))
story.append(P(
    "The same machinery is an instrument for the science of creativity, not just its "
    "engineering. Four directions look most promising.", "bodyni"))
story.append(P(
    "<b>An empirical factor structure.</b> The behavioral-novelty gate does something no "
    "hand-built battery does: it discovers axes of textual creativity that are "
    "<i>behaviorally independent by construction</i> — in our runs, word-level novelty, "
    "combination-level novelty, structural variety, insertion locality, and appropriateness "
    "gates. Regressing human creativity ratings onto these axes would yield a data-driven, "
    "fully interpretable decomposition of what readers mean by “creative” — which "
    "axes carry weight, which are redundant, and whether the weights differ across genres "
    "and readers. Every discovered scorer is a falsifiable hypothesis; human ratings are "
    "the experiment."))
story.append(P(
    "<b>Domain transfer as a universality probe.</b> In a side study scoring acclaimed "
    "song lyrics against generic ones, word-rarity <i>inverted</i> — plain-diction masters "
    "score low on rarity — while combination-level novelty transferred cleanly, preferring "
    "every acclaimed original over its flattened paraphrase. This suggests a testable "
    "hypothesis: <i>unusual combinations of ordinary words are the domain-general core of "
    "textual creativity, while rare vocabulary is a domain-specific costume.</i> The "
    "harness makes such cross-domain tests nearly free."))
story.append(P(
    "<b>A measurement-complexity ladder.</b> Our runs empirically locate which facets of "
    "creativity are measurable with which resources: word-frequency statistics suffice for "
    "freshness; co-occurrence statistics for combinational surprise; embeddings are needed "
    "for semantic distance and topical fit; and judging whether a sustained image is "
    "<i>earned</i> plausibly requires a full language model. The adversary tells you when a "
    "rung is exhausted: attacks from within the level stop working, and the only effective "
    "attacks come from the level above (our statistically-identical, semantically-opposed "
    "pairs). Charting this ladder — the minimum machinery required for each judgment — "
    "would give creativity measurement the kind of resource-complexity map that "
    "computational linguistics has for syntax and semantics."))
story.append(P(
    "<b>Open questions the harness can answer cheaply.</b> Is the peak of the "
    "inverted U stable across genres and readers, or a moving target? Do humans actually "
    "prefer minimal-edit brilliance (high concentration of change), or is that an "
    "editor's aesthetic? Does appropriateness act as a hard gate in human judgment "
    "(a conjunctive product, as our survivors assume) or as a soft trade-off? Each "
    "question reduces to one scorer-versus-human-ratings experiment on a few hundred "
    "pairs."))

# ── 7 Related work ────────────────────────────────────────────────────
story.append(P("7&nbsp;&nbsp;Related Work", "h1"))
story.append(P(
    "Our loop belongs to the family of LLM-guided evolutionary search over programs, most "
    "prominently FunSearch (Romera-Paredes et al. 2024), which pairs an LLM proposer with a "
    "programmatic evaluator; we add an adversarial data-growth role and honesty gates "
    "targeted at the failure modes of subjective evaluation. Adversarially-collected "
    "benchmarks that grow with the model under test were popularized by Dynabench (Kiela "
    "et al. 2021). Program-space search by selection descends from genetic programming "
    "(Koza 1992). On the creativity-measurement side, we build on the two-factor "
    "definition (Runco and Jaeger 2012), moderate-novelty preference (Berlyne 1971), "
    "computational novelty measures based on semantic distance (Beaty and Johnson 2021; "
    "Olson et al. 2021; Johnson et al. 2022), and lexical-diversity measurement (McCarthy "
    "and Jarvis 2010). Our contribution is not a new creativity theory but evidence that a "
    "gated adversarial loop can re-derive the theory's structure as executable code, and an "
    "ablation isolating how much the proposing model matters.", "bodyni"))

# ── 7 Limitations ─────────────────────────────────────────────────────
story.append(P("8&nbsp;&nbsp;Limitations", "h1"))
story.append(P(
    "The “more/less creative” labels were authored by LLMs; the blind judge panel "
    "(Sec. 5.5) validates their consistency across independent model raters at 91%, and an "
    "external transfer test exists for one scorer, but human ratings remain the essential "
    "validation (a blinded human-rating instrument has been fielded; results pending). "
    "Each agent arm was run once — trajectory details are surely seed-dependent, though "
    "the conjunctive convergence appeared in all three arms and the blind-search family "
    "recurred across seeds. Separations are modest in absolute terms (0.1–0.4 on a 0–1 "
    "scale) because the test set is deliberately adversarial; all headline separations now "
    "carry bootstrap CIs and the expanded 26-case core excludes zero for every reported "
    "scorer. All arms received the same orchestrated lesson-passing between generations; "
    "our ablation isolates the proposing model, not the orchestration. One harness flaw "
    "found and documented: the keep-worst rule for adversarial cases must require the "
    "champion to actually fail, or exhausted attacks dilute the test set and inflate "
    "measured skill. Finally, pre-trained semantic resources were unavailable in our "
    "sandbox, making the frequency-statistics ceiling unavoidable rather than chosen — and "
    "the anti-memorization gate's ban on inline lexicons contributes to that ceiling; a "
    "registered-resource mechanism would relax it safely. For reproducibility we release "
    "the full harness, every scorer's code with per-case behavioral fingerprints, the "
    "primitive library and search configuration, all test tiers with provenance, and the "
    "exact word-frequency resource and normalization pipeline.", "bodyni"))

# ── 8 Conclusion ──────────────────────────────────────────────────────
story.append(P("9&nbsp;&nbsp;Conclusion", "h1"))
story.append(P(
    "A small agent ensemble — one role writing scoring code, one role writing counter-"
    "examples, and a deterministic referee enforcing validity, non-memorization, behavioral "
    "novelty, and usefulness — three times converged on the two-factor structure of "
    "creativity as short, readable Python, and our ablation locates the cause precisely: "
    "not static fitness (no enrichment among 12,000 random programs) but adversarial "
    "survival. Swapping the proposing model for one far smaller — even at strictly matched "
    "budget — changed the journey but not the destination: comparable acceptance rates, "
    "statistically indistinguishable final champions, the same convergent design. And when "
    "we freed the hypothesis space while keeping the gates, the system delivered what "
    "theory-first proposing never did: a non-intuitive, externally transferring, "
    "falsification-tested scorer whose reading — creative edits are few and land where the "
    "information lives — is a genuine, checkable hypothesis about creativity itself. The practical recipe we take away is that when searching for "
    "evaluation metrics with LLMs, <b>invest in the referee and the adversary before "
    "investing in a bigger proposer</b> — and always keep one test set the process is never "
    "allowed to touch.", "bodyni"))

# ── References ────────────────────────────────────────────────────────
story.append(P("References", "h1"))
refs = [
    "Beaty, R. E., and Johnson, D. R. 2021. Automating creativity assessment with SemDis. "
    "<i>Behavior Research Methods</i> 53:757–780.",
    "Berlyne, D. E. 1971. <i>Aesthetics and Psychobiology</i>. Appleton-Century-Crofts.",
    "Johnson, D. R.; Kaufman, J. C.; et al. 2022. Divergent semantic integration (DSI): "
    "Extracting creativity from narratives. <i>Behavior Research Methods</i> 55:3726–3759.",
    "Kiela, D.; Bartolo, M.; Nie, Y.; et al. 2021. Dynabench: Rethinking benchmarking in "
    "NLP. In <i>Proc. NAACL</i>, 4110–4124.",
    "Koza, J. R. 1992. <i>Genetic Programming: On the Programming of Computers by Means of "
    "Natural Selection</i>. MIT Press.",
    "McCarthy, P. M., and Jarvis, S. 2010. MTLD, vocd-D, and HD-D: A validation study of "
    "sophisticated approaches to lexical diversity assessment. <i>Behavior Research "
    "Methods</i> 42:381–392.",
    "Olson, J. A.; Nahas, J.; Chmoulevitch, D.; Cropper, S. J.; and Webb, M. E. 2021. "
    "Naming unrelated words predicts creativity. <i>PNAS</i> 118(25).",
    "Romera-Paredes, B.; Barekatain, M.; Novikov, A.; et al. 2024. Mathematical discoveries "
    "from program search with large language models. <i>Nature</i> 625:468–475.",
    "Runco, M. A., and Jaeger, G. J. 2012. The standard definition of creativity. "
    "<i>Creativity Research Journal</i> 24(1):92–96.",
]
for r in refs:
    story.append(P(r, "ref"))

# ── Document assembly: page 1 = title band + two columns; rest = two columns ──
PAGE_W, PAGE_H = letter
M = 0.72 * inch
GUTTER = 0.28 * inch
COL_W = (PAGE_W - 2 * M - GUTTER) / 2

title_h = 3.98 * inch
f_title = Frame(M, PAGE_H - M - title_h, PAGE_W - 2 * M, title_h, id="title")
f_l1 = Frame(M, M, COL_W, PAGE_H - 2 * M - title_h, id="l1")
f_r1 = Frame(M + COL_W + GUTTER, M, COL_W, PAGE_H - 2 * M - title_h, id="r1")
f_l = Frame(M, M, COL_W, PAGE_H - 2 * M, id="l")
f_r = Frame(M + COL_W + GUTTER, M, COL_W, PAGE_H - 2 * M, id="r")

doc = BaseDocTemplate(OUT, pagesize=letter,
                      leftMargin=M, rightMargin=M, topMargin=M, bottomMargin=M)
doc.addPageTemplates([
    PageTemplate(id="First", frames=[f_title, f_l1, f_r1]),
    PageTemplate(id="TwoCol", frames=[f_l, f_r]),
])
story.insert(0, NextPageTemplate("TwoCol"))
doc.build(story)
print("wrote", OUT)
