let CAPACITY_WH = 625; // your battery capacity in Wh
let START_SOC = 0.2;
let TARGET_SOC = 0.8;
let EFFICIENCY = 0.85; // calibrate if needed
let TARGET_WH = (CAPACITY_WH * (TARGET_SOC - START_SOC)) / EFFICIENCY;

let startEnergy = null;

Timer.set(30000, true, function () {
  let st = Shelly.getComponentStatus("switch:0");
  if (!st.output) {
    startEnergy = null;
    return;
  }
  if (startEnergy === null) {
    startEnergy = st.aenergy.total;
    return;
  }
  let delivered = st.aenergy.total - startEnergy;
  if (delivered >= TARGET_WH) {
    Shelly.call("Switch.Set", { id: 0, on: false });
    print("Target reached: " + delivered.toFixed(1) + " Wh charged");
  }
});
