import sys
from pathlib import Path

from genealogy_kg.hourglass import hourglass_positions
from genealogy_kg.module import GenealogyKG

repo, xref = sys.argv[1], sys.argv[2]
with GenealogyKG(repo_root=Path(repo)) as kg:
    hp = hourglass_positions(kg.store, xref)
    print(
        "anc",
        hp.n_ancestors,
        "desc",
        hp.n_descendants,
        "skipped",
        hp.skipped_edges,
        "nodes",
        len(hp.wood_points),
    )
    for pid, g in sorted(hp.generation.items(), key=lambda t: t[1]):
        n = kg.store.node(pid) or {}
        print(g, pid, n.get("name"), hp.person_positions[pid].round(2))
