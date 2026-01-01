export const logPerformance = (label, startTime) => {
  const duration = performance.now() - startTime;
  console.log(`[PERF] ${label}: ${duration.toFixed(2)}ms`);
  if (duration > 1500) {
    console.warn(`[PERF] ${label} exceeded budget of 1500ms`);
  }
};
