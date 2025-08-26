Please analyze this repo and determine a series of probing tests to try and push for results which maximize the following properties:

- accuracy: minimal total BER (i.e. 0.065 achieved or 0.00)
- consistency against realistic environmental noise
- realistic components pulled from actual purchasable products
- lower priced products where possible (figuring out which ones are critical and which are less important for scaling)
- total average speed / cycle time (though schemes which use an initial/periodic slow calibration or slow input read over many cycles may be acceptable - especially if the subsequent cycles for multiple layers are short)
- uses analog cycling ("path B") to emulate multiple hidden transformer layers before a final camera readout (though prefer accuracy first with single-path runs before attempting looping)
- shows both analog input (read from static "cold" etched glass/crystal with its own seek/read movement delays) and digital input (read from digital-to-analog "hot" emitters, delayed by the device + the digital data lookup speed).
- uses inherent delays from either input method intelligently as slack for the rest of the system
- aims for highest achievable throughputs, given all other constraints.  Aims to characterize tiers of quality/quantity vs cost/complexity/stability.
- above all aims for realism.  NEVER sacrifices realistic conditions and realistic products for easy simulation cheats (except as well-marked temporary measures while calibrating)
 
With those heuristics in mind, please proceed to develop testing plans using and improving our simulation code to try and narrow down best simulation parameters and characterize what we're capable of.  Where you see missing, incorrect, or needing-refinement features please suggest the code changes and keep moving on

Try to proceed with one probe at a time, analyzing the data, then adjusting accordingly for the next probe.   Try to do this all by running your own test queries, and don't rely on the human user and dashboard at all if you can.  Try to run as many probes and tests per session one after the other as you can manage before hitting session limits.

Be careful to make non-destructive changes where possible, at least when modifying params/probes, so you can still access the history of progress.  (Functional code changes can still be destructive if necessary)  

Try to give brief layman summaries of progress on what was achieved where relevant, to mark progress.  Try to track and update the history of what was tried to avoid repeating past mistakes.

Please proceed with designing your next test probes.

UPDATE: we now use a queue design to set probes to run, which is run by an external process.

APPEND ONLY to queue/probes.jsonl
NEVER modify queue/completed.jsonl