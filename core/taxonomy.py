# core/taxonomy.py — Semantic relations and taxonomies for ingredients, recipes, inventory.
#
# Taxonomy is a separate semantic layer; node ids may match data model ids or names.
# Caller is responsible for populating and syncing with the data model.
#
# Edge direction:
# - is_a: (child, parent) so source=child, target=parent (e.g. tomate is_a verdura).
# - part_of: (part, whole) so source=part, target=whole.

from __future__ import annotations

from collections import deque
from typing import Optional

# Supported relationship types (documented for queries and traversal).
IS_A = "is_a"       # Subtype / classification: child is_a parent.
PART_OF = "part_of" # Meronymy: part part_of whole.


class Taxonomy:
    """
    Generic taxonomy: nodes and directed edges with optional relationship type.
    Used by IngredientTaxonomy, RecipeTaxonomy, InventoryTaxonomy.
    Supports multiple roots. Node ids are strings (names or str(id)).
    """

    def __init__(self) -> None:
        self._nodes: set[str] = set()
        # Edges: (source, target, relationship_type). For is_a: source=child, target=parent.
        self._edges: list[tuple[str, str, str]] = []
        self._edges_by_source: dict[str, list[tuple[str, str]]] = {}  # source -> [(target, type), ...]
        self._edges_by_target: dict[str, list[tuple[str, str]]] = {}  # target -> [(source, type), ...]

    def add_node(self, node_id: str, name: Optional[str] = None) -> None:
        """Register a node. node_id is the canonical key; name is optional display (stored only if needed)."""
        self._nodes.add(node_id)
        if node_id not in self._edges_by_source:
            self._edges_by_source[node_id] = []
        if node_id not in self._edges_by_target:
            self._edges_by_target[node_id] = []

    def add_relationship(
        self,
        source: str,
        target: str,
        relationship_type: str = IS_A,
    ) -> None:
        """
        Add a directed edge from source to target with the given type.
        For is_a: source=child, target=parent. For part_of: source=part, target=whole.
        """
        self._nodes.add(source)
        self._nodes.add(target)
        self._edges.append((source, target, relationship_type))
        if source not in self._edges_by_source:
            self._edges_by_source[source] = []
        self._edges_by_source[source].append((target, relationship_type))
        if target not in self._edges_by_target:
            self._edges_by_target[target] = []
        self._edges_by_target[target].append((source, relationship_type))

    def get_children(self, node_id: str) -> list[str]:
        """Nodes that have an edge to this node (incoming). For is_a (child, parent), these are the children (this node is parent)."""
        if node_id not in self._edges_by_target:
            return []
        return [s for s, _ in self._edges_by_target[node_id]]

    def get_parents(self, node_id: str) -> list[str]:
        """Nodes that have an edge from this node (outgoing). For is_a (child, parent), these are the parents (this node is child)."""
        if node_id not in self._edges_by_source:
            return []
        return [t for t, _ in self._edges_by_source[node_id]]

    def get_related(self, node_id: str, relationship_type: str) -> list[str]:
        """
        For outgoing edges of this type: return targets (e.g. parents for is_a from child).
        For incoming edges of this type: return sources (e.g. children for is_a to parent).
        Returns union of both directions so "related" by that type is symmetric in result.
        """
        if node_id not in self._nodes:
            return []
        out = [t for t, rt in self._edges_by_source.get(node_id, []) if rt == relationship_type]
        inc = [s for s, rt in self._edges_by_target.get(node_id, []) if rt == relationship_type]
        return list(dict.fromkeys(out + inc))

    def has_relationship(self, a: str, b: str, relationship_type: str) -> bool:
        """True if there is an edge (a, b, type) or (b, a, type)."""
        if (b, relationship_type) in self._edges_by_source.get(a, []):
            return True
        if (a, relationship_type) in self._edges_by_source.get(b, []):
            return True
        return False

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes


def find_related_items(
    taxonomy: Taxonomy,
    node_id: str,
    max_depth: Optional[int] = None,
    limit: Optional[int] = None,
) -> list[tuple[str, int]]:
    """
    Find nodes related to node_id by traversal (BFS). Returns list of (node_id, distance).
    distance 0 = self, 1 = direct neighbor, etc. Order: by distance, then by node_id.
    """
    if not taxonomy.has_node(node_id):
        return []
    if max_depth is not None and max_depth < 0:
        return []
    result: list[tuple[str, int]] = []
    seen: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(node_id, 0)])
    while queue:
        n, d = queue.popleft()
        if n in seen:
            continue
        seen.add(n)
        if max_depth is not None and d > max_depth:
            continue
        result.append((n, d))
        if limit is not None and len(result) >= limit:
            break
        for neighbor in taxonomy.get_children(n) + taxonomy.get_parents(n):
            if neighbor not in seen:
                queue.append((neighbor, d + 1))
    result.sort(key=lambda x: (x[1], x[0]))
    if limit is not None:
        result = result[:limit]
    return result


# --- Domain taxonomies (facades over Taxonomy) ---------------------------------

class IngredientTaxonomy:
    """
    Taxonomy for ingredients. Nodes keyed by ingredient name or id (string).
    Caller populates and syncs with data model.
    """

    def __init__(self) -> None:
        self._taxonomy = Taxonomy()

    def add_ingredient(self, ingredient_id: str) -> None:
        self._taxonomy.add_node(ingredient_id)

    def add_is_a(self, child: str, parent: str) -> None:
        self._taxonomy.add_relationship(child, parent, IS_A)

    def add_part_of(self, part: str, whole: str) -> None:
        self._taxonomy.add_relationship(part, whole, PART_OF)

    def get_ingredient_ancestors(self, ingredient_id: str) -> list[str]:
        """All ancestors following is_a (parents, grandparents, ...)."""
        out: list[str] = []
        stack = list(self._taxonomy.get_parents(ingredient_id))
        seen = {ingredient_id}
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            for p in self._taxonomy.get_parents(n):
                if p not in seen:
                    stack.append(p)
            out.append(n)
        return out

    def get_ingredient_related(self, ingredient_id: str, relationship_type: str) -> list[str]:
        return self._taxonomy.get_related(ingredient_id, relationship_type)

    @property
    def taxonomy(self) -> Taxonomy:
        return self._taxonomy


class RecipeTaxonomy:
    """
    Taxonomy for recipes. Nodes keyed by recipe id (string) or name.
    Caller populates and syncs with data model.
    """

    def __init__(self) -> None:
        self._taxonomy = Taxonomy()

    def add_recipe(self, recipe_id: str) -> None:
        self._taxonomy.add_node(recipe_id)

    def add_is_a(self, child: str, parent: str) -> None:
        self._taxonomy.add_relationship(child, parent, IS_A)

    def add_part_of(self, part: str, whole: str) -> None:
        self._taxonomy.add_relationship(part, whole, PART_OF)

    def get_recipe_categories(self, recipe_id: str) -> list[str]:
        """Parents via is_a (category-style)."""
        return self._taxonomy.get_parents(recipe_id)

    def get_related_recipes(self, recipe_id: str, relationship_type: str) -> list[str]:
        return self._taxonomy.get_related(recipe_id, relationship_type)

    @property
    def taxonomy(self) -> Taxonomy:
        return self._taxonomy


class InventoryTaxonomy:
    """
    Taxonomy for inventory items. Nodes keyed by inventory_item_id (string) or name.
    Caller populates and syncs with data model. FamilyInventory remains source of truth for family.
    """

    def __init__(self) -> None:
        self._taxonomy = Taxonomy()

    def add_item(self, item_id: str) -> None:
        self._taxonomy.add_node(item_id)

    def add_is_a(self, child: str, parent: str) -> None:
        self._taxonomy.add_relationship(child, parent, IS_A)

    def add_part_of(self, part: str, whole: str) -> None:
        self._taxonomy.add_relationship(part, whole, PART_OF)

    def get_inventory_ancestors(self, item_id: str) -> list[str]:
        """All ancestors following is_a."""
        out: list[str] = []
        stack = list(self._taxonomy.get_parents(item_id))
        seen = {item_id}
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            for p in self._taxonomy.get_parents(n):
                if p not in seen:
                    stack.append(p)
            out.append(n)
        return out

    def get_related_inventory_items(self, item_id: str, relationship_type: str) -> list[str]:
        return self._taxonomy.get_related(item_id, relationship_type)

    @property
    def taxonomy(self) -> Taxonomy:
        return self._taxonomy
