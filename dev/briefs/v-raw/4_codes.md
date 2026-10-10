CODE LIST — collections systems (use the API value in tool calls; the spoken name when talking)

Products (get_account "type" -> spoken name)
| API value | Spoken name |
|---|---|
| credit_card | Visa card ending {card_last4} |
| personal_loan | personal finance loan |
| car_loan | vehicle finance agreement |

Outcome codes (close_call "outcome")
| Code | API value | Meaning |
|---|---|---|
| PRM | promise | at least one promise recorded |
| PAI | paid | customer already paid everything |
| TR | transferred | handed to a person |
| NP | no_promise | verified customer, no promise |
| NV | not_verified | identity not verified |
| NR | not_reached | the customer was not on the line |

Reason codes (close_call "reason")
| Code | API value | Used with |
|---|---|---|
| RST | restructuring | TR |
| HUM | human | TR |
| SUP | support | TR |
| REF | refused | NP |
| HSH | hardship | NP |
| DSP | dispute | NP |
| SVC | service_error | NP |
| FLD | failed | NV |
| DCL | declined | NV |
| CBK | callback | NR |
| NCB | no_callback | NR |
| WRN | wrong_number | NR |
| DEC | deceased | NR |
| UNC | unclear | NR |

Note reasons (add_note "reason"): REF refused, HSH hardship, DSP dispute, PAI paid, SVC service_error.
Transfer queues (transfer_to_agent "queue"): RST restructuring, SUP support, GEN general.
