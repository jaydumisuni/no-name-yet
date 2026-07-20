from __future__ import annotations

from pathlib import Path

from main_review.static_status_review import run_static_status_review
from main_review.static_transfer_25_review import run_static_transfer_25_review


ELIXIR_ROOT = "required-discriminator-removal-error-accepted-as-success"
SCALA_ROOT = "failed-compilation-leaves-speculative-repl-state-advanced"
LUA_ROOT = "async-cleanup-recomputes-context-dependent-registry-key"


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_elixir_transform_must_validate_required_discriminator(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "apply.ex",
        """
defmodule Module.Types.Apply do
  @builtins [
    {Map, :from_struct, [{[open_map()], open_map(__struct__: not_set())}]}
  ]

  @struct_key atom([:__struct__])

  defp remote_apply(Map, :from_struct, _info, [map] = args_types, stack) do
    case map_update(map, @struct_key, not_set(), false, true) do
      {_value, descr, _errors} -> {:ok, return(descr, args_types, stack)}
      :badmap -> {:error, badremote(Map, :from_struct, args_types)}
      {:error, _errors} -> {:ok, map}
    end
  end

  defp remote_apply(Map, :delete, _info, args, stack), do: {:ok, {args, stack}}
end
""",
    )

    result = run_static_transfer_25_review(tmp_path, ["apply.ex"])

    assert ELIXIR_ROOT in _roots(result)


def test_elixir_transform_requiring_discriminator_is_clean(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "apply.ex",
        """
defmodule Module.Types.Apply do
  @builtins [
    {Map, :from_struct, [{[open_map(__struct__: atom())], open_map(__struct__: not_set())}]}
  ]

  @struct_key atom([:__struct__])

  defp remote_apply(Map, :from_struct, info, [map] = args_types, stack) do
    case remote_apply(info, args_types, stack) do
      {:ok, _type} ->
        case map_update(map, @struct_key, not_set(), false, true) do
          {_value, descr, _errors} -> {:ok, return(descr, args_types, stack)}
          _ -> {:error, badremote(Map, :from_struct, args_types)}
        end

      other ->
        other
    end
  end
end
""",
    )

    result = run_static_transfer_25_review(tmp_path, ["apply.ex"])

    assert ELIXIR_ROOT not in _roots(result)


def test_scala_compile_failure_must_rollback_speculative_repl_state(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "ReplDriver.scala",
        """
case class State(
  objectIndex: Int,
  valIndex: Int,
  invalidObjectIndexes: Set[Int]
)

class ReplDriver:
  given State =
    val state0 = newRun(istate, parsed.reporter)
    state0.copy(context = state0.context.withSource(parsed.source))

  compiler
    .compile(parsed)
    .fold(
      displayErrors,
      { case (unit, newState: State) => newState }
    )
""",
    )

    result = run_static_transfer_25_review(tmp_path, ["ReplDriver.scala"])

    assert SCALA_ROOT in _roots(result)


def test_scala_compile_failure_returning_preinput_state_is_clean(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "ReplDriver.scala",
        """
case class State(
  objectIndex: Int,
  valIndex: Int,
  invalidObjectIndexes: Set[Int]
):
  def afterFailedCompilation(index: Int): State =
    copy(objectIndex = index, invalidObjectIndexes = invalidObjectIndexes + index)

class ReplDriver:
  given State =
    val state0 = newRun(istate, parsed.reporter)
    state0.copy(context = state0.context.withSource(parsed.source))

  compiler
    .compile(parsed)
    .fold(
      (errors, errState) =>
        displayErrors(errors, errState)
        istate.afterFailedCompilation(errState.objectIndex),
      { case (unit, newState: State) => newState }
    )
""",
    )

    result = run_static_transfer_25_review(tmp_path, ["ReplDriver.scala"])

    assert SCALA_ROOT not in _roots(result)


def test_lua_timer_cleanup_must_not_recompute_request_context_key(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "queue.lua",
        """
local workspaces = require "kong.workspaces"

local function make_queue_key(name)
  return string.format("%s.%s", workspaces.get_workspace_id(), name)
end

local queues = setmetatable({}, {
  __newindex = function(self, name, queue)
    return rawset(self, make_queue_key(name), queue)
  end,
  __index = function(self, name)
    return rawget(self, make_queue_key(name))
  end
})

local function get_or_create_queue(name, queue)
  kong.timer:named_at("queue " .. name, 0, function(_, q)
    q:process_once()
    queues[name] = nil
  end, queue)
  queues[name] = queue
end
""",
    )

    result = run_static_transfer_25_review(tmp_path, ["queue.lua"])

    assert LUA_ROOT in _roots(result)


def test_lua_timer_cleanup_using_captured_explicit_key_is_clean(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "queue.lua",
        """
local workspaces = require "kong.workspaces"

local function make_queue_key(name)
  return string.format("%s.%s", workspaces.get_workspace_id(), name)
end

local queues = {}

local function get_or_create_queue(name, queue)
  local key = make_queue_key(name)
  queue.key = key
  queues[key] = queue
  kong.timer:named_at("queue " .. key, 0, function(_, q)
    q:process_once()
    queues[q.key] = nil
  end, queue)
end
""",
    )

    result = run_static_transfer_25_review(tmp_path, ["queue.lua"])

    assert LUA_ROOT not in _roots(result)


def test_normal_static_status_path_admits_transfer_25_root(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "queue.lua",
        """
local workspaces = require "kong.workspaces"

local function make_queue_key(name)
  return string.format("%s.%s", workspaces.get_workspace_id(), name)
end

local queues = setmetatable({}, {
  __newindex = function(self, name, queue)
    return rawset(self, make_queue_key(name), queue)
  end,
  __index = function(self, name)
    return rawget(self, make_queue_key(name))
  end
})

kong.timer:named_at("queue " .. name, 0, function(_, q)
  queues[name] = nil
end, queue)
""",
    )

    result = run_static_status_review(tmp_path, ["queue.lua"])

    assert LUA_ROOT in _roots(result)
