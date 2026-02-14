
var f = new File;
f.createForWriting("ln_props.txt");

f.outTextLn("========================================");
f.outTextLn("Inspecting LocalNormalization Properties");
f.outTextLn("========================================");

var ln = new LocalNormalization;

// Specific properties check based on screenshot
f.outTextLn("Checking specific properties:");
var potentialProps = [
    "referenceFrameGeneration",
    "referenceGenerationMode",
    "generationMode",
    "integrateReference",
    "maximumIntegratedFrames",
    "growthFactor",
    "psfType",
    "noGuiding"
];

for (var i = 0; i < potentialProps.length; i++) {
    var p = potentialProps[i];
    if (ln[p] !== undefined) {
        f.outTextLn("  Existing Prop: " + p + " = " + ln[p]);
    } else {
        f.outTextLn("  Missing Prop: " + p);
    }
}

// Print all properties (if enumerable)
f.outTextLn("\nAll Enumerable Properties:");
for (var key in ln) {
    if (typeof (ln[key]) !== "function")
        f.outTextLn(key + " = " + ln[key]);
}

f.close();
console.writeln("Inspection written to ln_props.txt");
