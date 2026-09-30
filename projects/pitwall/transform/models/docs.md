{% docs meeting_key %}
Identifier of a Grand Prix weekend (a "meeting"): one race weekend at one circuit, e.g. the 2025 Chinese Grand Prix is 1255.
{% enddocs %}

{% docs session_key %}
Identifier of one on-track session. pitwall only keeps the two kinds of race: the Sunday **Race** and the shorter Saturday **Sprint**.
{% enddocs %}

{% docs driver_number %}
The driver's permanent car number (e.g. 1, 44, 81). Unique within a session.
{% enddocs %}

{% docs lap_number %}
Lap counter within a session, starting at 1. A lap is one full tour of the circuit.
{% enddocs %}

{% docs compound %}
Tyre type: SOFT (fastest, wears out quickly), MEDIUM, HARD (slowest, lasts longest), INTERMEDIATE and WET (for rain). UNKNOWN when the source does not say.
{% enddocs %}

{% docs tyre_age_laps %}
How many laps this set of tyres had already done when the lap started. Sets can be reused from earlier sessions, so a stint may start above 0.
{% enddocs %}

{% docs position %}
Running order: 1 is the leader. Taken from the latest position update recorded before the lap ended.
{% enddocs %}

{% docs neutralisation %}
`SC` if the Safety Car was on track during this lap, `VSC` for the Virtual Safety Car, `RED` if the race was stopped with a red flag on this lap, empty otherwise. Everyone drives slowly under either, so these laps say nothing about tyre wear, and pit stops cost less time.
{% enddocs %}

{% docs ingested_at %}
When pitwall downloaded this record from OpenF1 (UTC).
{% enddocs %}
