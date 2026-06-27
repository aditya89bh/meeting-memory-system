# Shared memory history example

These three transcripts belong to the same project (Project Atlas) across three
weeks. Importing them into a single database builds up persistent organizational
memory, so later queries can span every meeting.

```
Meeting 1 (kickoff)        Meeting 2 (weekly sync)      Meeting 3 (beta review)
        \                          |                          /
         \________________ shared database ___________________/
```

## Import all three into one database

```bash
meeting-memory import examples/history/meeting1.txt --db atlas.db
meeting-memory import examples/history/meeting2.txt --db atlas.db
meeting-memory import examples/history/meeting3.txt --db atlas.db
```

## Ask questions across the whole history

```bash
# What decisions have we made?
meeting-memory list --db atlas.db --type decision

# Which risks keep appearing? (the vendor API risk recurs every week)
meeting-memory list --db atlas.db --type risk

# What is still open?
meeting-memory list --db atlas.db --type open_loop,commitment

# Overall picture
meeting-memory stats --db atlas.db
meeting-memory meetings --db atlas.db
```

Re-running any `import` is a no-op: the transcript hash is already recorded, so
the meeting is reported as already imported and nothing is duplicated.
