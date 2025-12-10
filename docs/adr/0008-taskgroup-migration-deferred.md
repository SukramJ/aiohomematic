# ADR 0008: TaskGroup Migration Deferred

## Status

Deferred

## Context

Python 3.11 introduced `asyncio.TaskGroup` for structured concurrency with automatic cleanup and error propagation. A proposal was made to migrate `BackgroundScheduler` to use TaskGroup.

Current implementation in `central/scheduler.py`:

- Uses asyncio with a main scheduler loop
- Individual task management via `create_task()`
- Sequential job execution by design
- Graceful shutdown via `asyncio.CancelledError`

Proposed change:

```python
class ManagedTaskGroup:
    async def __aenter__(self) -> Self:
        self._tg = asyncio.TaskGroup()
        await self._tg.__aenter__()
        return self

    def create_task(self, *, coro: Coroutine[Any, Any, T], name: str) -> asyncio.Task[T]:
        task = self._tg.create_task(coro, name=f"{self._name}.{name}")
        return task
```

## Decision

**Defer this migration.** Keep the current task management approach.

## Rationale

### 1. Current Approach Is Sound

The scheduler already implements the key benefits of TaskGroup:

- Graceful shutdown via `asyncio.CancelledError`
- Job abstraction with clear lifecycle
- Proper cleanup on error or shutdown

### 2. TaskGroup Benefits Already Present

The main advantages of TaskGroup are:

- Automatic cleanup of child tasks on error
- Error propagation to parent

Both are already implemented in the current design through explicit task tracking and cancellation handling.

### 3. Sequential Execution Is Intentional

The current scheduler runs jobs **sequentially by design**. This is a deliberate choice:

- Prevents resource contention between jobs
- Ensures predictable execution order
- Simplifies debugging and reasoning about state

TaskGroup encourages parallelism, which may not be appropriate for all scheduler jobs.

### 4. Low Priority Improvement

Migration would be:

- Code churn without functional improvement
- Risk of subtle behavioral changes
- Testing overhead for no user-visible benefit

## Alternatives Considered

### Alternative 1: Full TaskGroup Migration (Deferred)

Replace all task management with TaskGroup.

**Deferred because**: Would require careful analysis of which jobs can safely run in parallel.

### Alternative 2: Hybrid Approach (Deferred)

Use TaskGroup for parallel-safe jobs, keep sequential for others.

**Deferred because**: Added complexity for marginal benefit.

### Alternative 3: Keep Current Design (Accepted)

Maintain the existing task management approach.

**Accepted because**: Working, well-tested, appropriate for the current workload.

## Reactivation Criteria

Consider TaskGroup adoption when:

- Significant scheduler refactoring is needed
- New parallel workloads are added that would benefit from structured concurrency
- A specific bug or limitation in current approach is identified

## Consequences

### Positive

- No migration effort or risk
- Proven stability maintained
- Sequential execution preserved

### Negative

- Not using latest Python idioms
- Manual task tracking instead of automatic cleanup

## Date

2025-12-10
