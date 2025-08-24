(add documentation as context then:)

Please analyze this repo and the provided documentation (DESIGN.md, README.md, context.md, tuning_assessment.md) and make a full report on your perception of what we're doing here, the purpose of this project, and next potential steps.





---


Okay now lets get to tuning.  Recommended path to start would be to confirm the ability to hit 0.065 in individual probes via examples/test.py.   See sub_0p065_tuned_no_autotune_path_a.json for a 6-iteration preset which managed to achieve 0.065 BER with two of the runs - probably best to try and isolate those into individual one-shot probes first, as we'd like to avoid using presets and the dashboard now in favor of fast iteration in an automated way.

Your task going forward will be to try and run individual probes and adjust your hypotheses, continuing to run probing tests (and/or making any requisite code changes) to narrow down this system towards our stated goals in TUNING.md.  Please run these tests yourself (i.e. don't just request them from me, the user) and try to fit in as many as you can before hitting response limits.  Good luck with this high-level science of tuning!

Note we are using Windows CMD 