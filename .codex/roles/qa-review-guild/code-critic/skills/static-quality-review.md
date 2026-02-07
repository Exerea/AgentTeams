# static-quality-review

## Trigger
- `local_flags.qa_review_required=true`
- コード差分を含む task

## Goal
品質回帰を未然に防ぎ、保守性を維持する。

## Procedure
1. `task_file_path` の scope と差分概要を確認する。
2. 複雑度、命名、責務分離、例外処理を点検する。
3. 重大度別に指摘を整理し `notes` に記録する。
4. 修正依頼または承認を handoff する。

## Output Format
- findings（critical/high/medium/low）
- pass/fail 判定
- 次 handoff（test-architect/coordinator）
