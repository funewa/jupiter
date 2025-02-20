# Tasks Generation

Tasks generation is a periodic action you must perform. It takes the _templates_ that are
[habits](habits.md), [chores](chores.md), [metrics](metrics.md) or [persons](persons.md) and turns them into real
[inbox tasks](inbox-tasks.md).

It needs to be performed daily usually.

The command itself is simply called `gen` and you can invoke it as:

```bash
$ jupiter gen
```

By default this will generate tasks with the `daily` period for today. But you can force other periods like so:

```bash
$ jupiter gen --period daily --period weekly --period monthly
```

It's the case that you'll want to run these other versions at the start of a week, month, quarter, or year.

Some things to note:

* The command is idempotent, so you can run it however many times you want and it'll do the right thing.
* Via the `--date` argument you can run generation for a date different than today - either in the future or in the
  past.
* You can limit it to habits, chores, metrics, or persons via the `--target` option.
* You can limit it for a particular project too via the `--project` option.
* You can filter for specific habits, chores, metrics, and persons.
* Check the help for more options via `jupiter gen --help`.
