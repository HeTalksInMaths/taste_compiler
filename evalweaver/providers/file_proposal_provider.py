"""File-exchange proposal provider.

Lets an interactive agent (a Claude Code session) — or a human — play the
role of the mutation LLM without any API credentials. Used with stepped
evolution (`evalweaver evolve --provider claude --step`):

1. At the end of generation N the loop calls prepare_requests(), which
   writes `request_genNN.json` into the exchange directory. It contains the
   full mutation context (probe registry + semantics, frontier code and
   coverage map, failed pairs, scorer contract) plus the exact response
   format.
2. Between invocations, the agent reads the request and writes
   `scorers_genNN.json` and/or `pairs_genNN.json`.
3. The next `--resume --step` invocation consumes the responses at the
   start of generation N: proposals are validated and join the population /
   candidate pool exactly as Bedrock tool-call output would.

Missing or malformed response files degrade to the deterministic genome
operators — identical failure semantics to the Bedrock provider.
"""

import json
import os

from evalweaver.artifacts import log


class FileProposalProvider:
    provider_name = "file-exchange"

    def __init__(self, exchange_dir):
        self.exchange_dir = exchange_dir
        os.makedirs(exchange_dir, exist_ok=True)

    def _path(self, name):
        return os.path.join(self.exchange_dir, name)

    def prepare_requests(self, gen, context, n_scorers, n_pairs):
        """Materialize the proposal request for generation `gen`."""
        request = {
            "generation": gen,
            "n_scorers_wanted": n_scorers,
            "n_pairs_wanted": n_pairs,
            "respond_with": {
                "scorers_file": self._path(f"scorers_gen{gen:02d}.json"),
                "scorers_format": {
                    "scorers": [{
                        "hypothesis": "<one-sentence interpretable claim: which probes and why they close the observed gap>",
                        "lineage": "mutation | recombination | novel_composition | blind_node_repair",
                        "targets_pair_types": ["<pair types from coverage_gaps>"],
                        "code": "def scorer(text, anchor, params):\n    ...",
                    }],
                },
                "pairs_file": self._path(f"pairs_gen{gen:02d}.json"),
                "pairs_format": {
                    "pairs": [{
                        "anchor": "<a social post, ideally from context anchors>",
                        "positive": "<genuinely better rewrite: concrete mechanism + result; NO invented numbers/names/guarantees>",
                        "negative": "<plausible but hollow: hype, fake mechanism, jargon>",
                        "pair_type": "hype_trap | fake_mechanism | specificity_trap | subtle_quality_gap | source_drift",
                        "label_contract": "<why positive is better>",
                        "intended_trap": "<which frontier weakness this attacks>",
                    }],
                },
            },
            "context": context,
        }
        path = self._path(f"request_gen{gen:02d}.json")
        with open(path, "w") as f:
            json.dump(request, f, indent=2, default=str)
        log("evolve", f"Proposal request written: {path}", "ok")

    def _read_response(self, name, key):
        path = self._path(name)
        if not os.path.exists(path):
            log("evolve", f"No response file {path}; falling back to deterministic operators", "warn")
            return []
        try:
            with open(path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            log("evolve", f"Unreadable response file {path} ({e}); ignoring", "warn")
            return []
        if isinstance(data, list):
            return data
        return data.get(key, [])

    def propose_scorers(self, context, count):
        gen = int(context.get("generation", 0))
        return self._read_response(f"scorers_gen{gen:02d}.json", "scorers")[:count]

    def propose_adversarial_pairs(self, context, count):
        gen = int(context.get("generation", 0))
        return self._read_response(f"pairs_gen{gen:02d}.json", "pairs")[:count]
