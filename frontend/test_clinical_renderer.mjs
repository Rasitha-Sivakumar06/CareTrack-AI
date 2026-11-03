import { decodeHtmlEntities, cleanTextForSpeech } from "./src/utils/clinicalFormatters.js";

console.log("=== Testing decodeHtmlEntities & cleanTextForSpeech ===");

// Test 1: Hexadecimal entity &#x4C; -> 'L' (Latest)
const sample1 = "&#x4C;atest";
const decoded1 = decodeHtmlEntities(sample1);
console.log(`[TEST 1 PASS] "&#x4C;atest" -> "${decoded1}"`);
if (decoded1 !== "Latest") {
  throw new Error(`Test 1 Failed: Expected "Latest", got "${decoded1}"`);
}

// Test 2: Multiple hex entities and medical readings
const sample2 = "&#x42;lood &#x47;lucose: &#x39;&#x38; mg/dL";
const decoded2 = decodeHtmlEntities(sample2);
console.log(`[TEST 2 PASS] Hex decoding -> "${decoded2}"`);
if (decoded2 !== "Blood Glucose: 98 mg/dL") {
  throw new Error(`Test 2 Failed: Expected "Blood Glucose: 98 mg/dL", got "${decoded2}"`);
}

// Test 3: Decimal entities
const sample3 = "Patient&#39;s fasting level &lt; 100 mg/dL &amp; SpO2 &gt;= 98&#37;";
const decoded3 = decodeHtmlEntities(sample3);
console.log(`[TEST 3 PASS] Decimal & Named decoding -> "${decoded3}"`);
if (decoded3 !== "Patient's fasting level < 100 mg/dL & SpO2 >= 98%") {
  throw new Error(`Test 3 Failed: "${decoded3}"`);
}

// Test 4: Degree entity and special characters
const sample4 = "Temp: 37&deg;C &plusmn; 0.5";
const decoded4 = decodeHtmlEntities(sample4);
console.log(`[TEST 4 PASS] Degree & PlusMinus decoding -> "${decoded4}"`);
if (decoded4 !== "Temp: 37°C ± 0.5") {
  throw new Error(`Test 4 Failed: "${decoded4}"`);
}

// Test 5: Markdown with HTML entities
const sample5 = "&#x4C;atest: **98 mg/dL** [S1]";
const decoded5 = decodeHtmlEntities(sample5);
console.log(`[TEST 5 PASS] Combined Entity + Markdown -> "${decoded5}"`);
if (decoded5 !== "Latest: **98 mg/dL** [S1]") {
  throw new Error(`Test 5 Failed: "${decoded5}"`);
}

// Test 6: cleanTextForSpeech with decoded entities
const sample6 = "&#x4C;atest reading: **98 mg/dL** [S1, S2]. Recommended repeat in 2 weeks.";
const speechClean = cleanTextForSpeech(sample6);
console.log(`[TEST 6 PASS] Speech cleaner strips citations and markdown after decoding: "${speechClean}"`);
if (!speechClean.includes("Latest reading: 98 mg/dL.") || speechClean.includes("[S1") || speechClean.includes("**")) {
  throw new Error(`Test 6 Failed: "${speechClean}"`);
}

console.log("\nALL CLINICAL CONTENT RENDERER ENTITY AND FORMATTING TESTS PASSED (6/6)!\n");
