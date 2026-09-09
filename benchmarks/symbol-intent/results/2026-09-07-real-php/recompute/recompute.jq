def delta_percent($before; $after): 100 * ($after / $before - 1);
. as $d |
($d.token_totals.text_manual.total - $d.token_totals.ast_integrated.total) as $saved |
{
  provenance: {source_commit:$d.source_commit, source_path:$d.source_path, scope:$d.scope},
  sum_validation: [ $d.token_totals | to_entries[] | {arm:.key, valid: ((.value.fresh + .value.cache_create + .value.cache_read + .value.output) == .value.total)} ],
  integrated_vs_text_percent_change_of_medians: ($d.medians.text_manual | keys | map(. as $k | {key:$k,value:delta_percent($d.medians.text_manual[$k];$d.medians.ast_integrated[$k])}) | from_entries),
  integrated_vs_text_percent_change_of_token_totals: delta_percent($d.token_totals.text_manual.total;$d.token_totals.ast_integrated.total),
  token_reduction_decomposition: ["fresh","cache_create","cache_read","output"] | map(. as $k | {category:$k, saved:($d.token_totals.text_manual[$k] - $d.token_totals.ast_integrated[$k]), fraction_of_total_reduction_percent:(100 * ($d.token_totals.text_manual[$k] - $d.token_totals.ast_integrated[$k]) / $saved)}),
  total_tokens_saved:$saved,
  output_token_reduction_percent: (100 * (1 - $d.token_totals.ast_integrated.output / $d.token_totals.text_manual.output)),
  campaign_total_tokens: ($d.token_totals | map(.total) | add)
}
