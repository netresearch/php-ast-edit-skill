def sumfield($key): map(.[$key]) | add;
def meanfield($key): (map(.[$key]) | add) / length;
def token_totals($key):
  map(.[$key]) | {
    fresh_input: sumfield("inputTokens"),
    cache_read_input: sumfield("cacheReadInputTokens"),
    cache_write_input: sumfield("cacheCreationInputTokens"),
    all_input: sumfield("totalInputTokens"),
    output: sumfield("outputTokens"),
    input_plus_output: sumfield("totalTokens")
  };
def groupstats:
  {
    variant: .[0].variant,
    runs: length,
    oracle_passes: (map(select(.oracle.passed)) | length),
    native_successes: (map(select(.native_subtype == "success" and .native_is_error == false)) | length),
    timeouts: (map(select(.timed_out)) | length),
    all_model_tokens: token_totals("all_model_tokens"),
    primary_model_tokens: token_totals("primary_model_tokens"),
    tool_calls: sumfield("tool_calls"),
    failed_tool_calls: sumfield("failed_tool_calls"),
    primary_model_rounds: sumfield("primary_model_rounds"),
    native_turns: sumfield("native_num_turns"),
    candidate_wall_ms: sumfield("candidate_wall_ms"),
    mean_candidate_wall_ms: meanfield("candidate_wall_ms"),
    native_list_price_usd: sumfield("native_list_price_usd")
  };
if length != 12 then error("Need all twelve retained observations") else . end
| {
    source_commit: .[0].source_commit,
    config_sha256: .[0].config_sha256,
    limitation: "Two tiny seed tasks, three paired repetitions per treatment. Provider cache state unknown; actual counters retained. USD values are native list-price estimates under subscription authentication. Human acceptance pending; no formal importer records created.",
    by_variant: (group_by(.variant) | map(groupstats)),
    by_task_and_variant: (group_by([.task_id, .variant]) | map({task_id: .[0].task_id} + groupstats)),
    pairs: (group_by([.task_id, .repetition]) | map(
      (map(select(.variant == "contextual_patch"))[0]) as $baseline |
      (map(select(.variant == "full_skill"))[0]) as $skill |
      {
        task_id: .[0].task_id,
        repetition: .[0].repetition,
        contextual_patch_run: $baseline.run_id,
        full_skill_run: $skill.run_id,
        contextual_patch_all_tokens: $baseline.all_model_tokens.totalTokens,
        full_skill_all_tokens: $skill.all_model_tokens.totalTokens,
        full_skill_token_difference_percent: (($skill.all_model_tokens.totalTokens / $baseline.all_model_tokens.totalTokens - 1) * 100),
        contextual_patch_wall_ms: $baseline.candidate_wall_ms,
        full_skill_wall_ms: $skill.candidate_wall_ms,
        contextual_patch_list_usd: $baseline.native_list_price_usd,
        full_skill_list_usd: $skill.native_list_price_usd
      }
    )),
    runs: (map({run_id, task_id, variant, repetition, primary_model_tokens, all_model_tokens, native_list_price_usd, candidate_wall_ms, tool_calls, failed_tool_calls, primary_model_rounds, native_num_turns, native_subtype, process_exit_code, timed_out, oracle_passed: .oracle.passed}))
  }
