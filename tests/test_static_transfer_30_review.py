from __future__ import annotations

from pathlib import Path

from main_review.static_transfer_30_review import run_static_transfer_30_review


def _run(tmp_path: Path, files: dict[str, str]):
    for relative, source in files.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    return run_static_transfer_30_review(tmp_path, files)


def _roots(result: dict) -> set[str]:
    return {str(item["root_cause"]) for item in result["findings"]}


def test_nth_formula_cannot_be_enumerated_as_bounded_sibling_positions(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        {
            "lib/CSS.pm": r'''
sub _equation {
  return [2, 2] if $_[0] =~ /even/;
}
sub _siblings { return [] }
sub _pc {
  my ($class, $args, $current) = @_;
  my @siblings = @{_siblings($current)};
  if (ref $args) {
    for my $i (0 .. $#siblings) {
      next if (my $result = $args->[0] * $i + $args->[1]) < 1;
      return undef unless my $sibling = $siblings[$result - 1];
      return 1 if $sibling eq $current;
    }
  }
  return undef;
}
'''
        },
    )

    assert "nth-selector-formula-enumerated-as-bounded-sibling-lookup" in _roots(result)


def test_nth_formula_is_clean_when_current_index_is_checked_algebraically(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        {
            "lib/CSS.pm": r'''
sub _equation { return [2, 0] }
sub _siblings { return [] }
sub _pc {
  my ($class, $args, $current) = @_;
  my @siblings = @{_siblings($current)};
  my $index;
  for my $i (0 .. $#siblings) {
    $index = $i, last if $siblings[$i] eq $current;
  }
  $index++;
  my $delta = $index - $args->[1];
  return 1 if $delta == 0;
  return $args->[0] != 0 && ($delta < 0) == ($args->[0] < 0) && $delta % $args->[0] == 0;
}
'''
        },
    )

    assert result["finding_count"] == 0


def test_recursive_list_cannot_use_unbounded_generated_union_hash(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        {
            "src/FSharp.Core/prim-types.fs": '''
[<StructuralEquality; StructuralComparison>]
type List<'T> =
   | ([]) : 'T list
   | (::) : Head: 'T * Tail: 'T list -> 'T list
''',
            "src/Compiler/AugmentWithHashCompare.fs": '''
let MakeBindingsForEqualityWithComparerAugmentation g tycon =
    let mkStructuralEquatable hashf equalsf = hashf, equalsf
    if tycon.IsUnionTycon then mkStructuralEquatable mkUnionHashWithComparer mkUnionEqualityWithComparer
    else []
''',
        },
    )

    assert "recursive-list-structural-hash-generated-without-tail-bounded-implementation" in _roots(result)


def test_recursive_list_hash_is_clean_with_custom_iterative_override(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        {
            "src/FSharp.Core/prim-types.fs": '''
[<StructuralEquality; StructuralComparison>]
type List<'T> =
   | ([]) : 'T list
   | (::) : Head: 'T * Tail: 'T list -> 'T list
   member private this.CustomHashCode(comparer) =
       let rec loop current acc =
           match current with
           | [] -> acc
           | head :: tail -> loop tail (combine acc head)
       loop this 0
''',
            "src/Compiler/AugmentWithHashCompare.fs": '''
let MakeBindingsForEqualityWithComparerAugmentation g tycon =
    if tyconRefEq g tcref g.list_tcr_canon && tycon.HasMember g "CustomHashCode" [] then
        callCustomHashCode()
    elif tycon.IsUnionTycon then mkStructuralEquatable mkUnionHashWithComparer mkUnionEqualityWithComparer
    else []
''',
        },
    )

    assert result["finding_count"] == 0


def test_bounded_deferred_free_cannot_reprepend_a_linked_remainder(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        {
            "lib/system/alloc.nim": '''
when defined(gcDestructors):
  template atomicPrepend(head, elem: untyped) =
    elem.next.storea head.loada
    head.storea elem

  proc addToSharedFreeListBigChunks(a: var MemRegion; c: PBigChunk) =
    atomicPrepend a.sharedFreeListBigChunks, c

  const MaxSteps = 20

  proc freeDeferredObjects(a: var MemRegion; root: PBigChunk) =
    var it = root
    var maxIters = MaxSteps
    while true:
      let rest = it.next.loada
      it.next.storea nil
      deallocBigChunk(a, it)
      if maxIters == 0:
        if rest != nil:
          addToSharedFreeListBigChunks(a, rest)
        break
      it = rest
      dec maxIters
      if it == nil: break

when defined(heaptrack):
  discard

proc rawAlloc(a: var MemRegion): pointer =
  let deferredFrees = atomicExchangeN(addr a.sharedFreeListBigChunks, nil, ATOMIC_RELAXED)
  if deferredFrees != nil:
    freeDeferredObjects(a, deferredFrees)
'''
        },
    )

    assert "detached-linked-list-tail-requeued-through-prepend-loses-chain" in _roots(result)


def test_deferred_free_is_clean_when_nodes_are_popped_one_at_a_time(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        {
            "lib/system/alloc.nim": '''
when defined(gcDestructors):
  template atomicPrepend(head, elem: untyped) =
    elem.next.storea head.loada
    head.storea elem

  proc addToSharedFreeListBigChunks(a: var MemRegion; c: PBigChunk) =
    atomicPrepend a.sharedFreeListBigChunks, c

  proc takeFromSharedFreeListBigChunks(a: var MemRegion): PBigChunk =
    result = a.sharedFreeListBigChunks
    if result != nil:
      a.sharedFreeListBigChunks = result.next
      result.next = nil

  proc freeDeferredObjects(a: var MemRegion) =
    for _ in 0..MaxSteps:
      let it = takeFromSharedFreeListBigChunks(a)
      if it == nil: break
      deallocBigChunk(a, it)

proc rawAlloc(a: var MemRegion): pointer =
  freeDeferredObjects(a)
'''
        },
    )

    assert result["finding_count"] == 0
