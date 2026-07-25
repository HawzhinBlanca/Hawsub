# Implementation Notes

## Keep the fork lean

The primary engineering risk is turning Hawsub into a second generic video suite.

Avoid this.

Reuse pyVideoTrans infrastructure, but isolate Hawsub-specific code in clearly owned modules.

## Biggest differentiation

Engineering effort should concentrate on:
1. context;
2. semantic interpretation;
3. natural Sorani generation;
4. terminology consistency;
5. subtitle-specific QC;
6. uncertainty detection.

## Hard rule

Do not deploy a newer model unless it wins the Hawsub benchmark.
