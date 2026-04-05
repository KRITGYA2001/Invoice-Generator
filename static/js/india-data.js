/* ============================================================
   BillMint — India Reference Data
   States · Cities · Countries + Alpine.js smart-select factory
   ============================================================ */

/* ── Indian States with GST state codes ── */
const INDIA_STATES = [
  { code: "35", name: "Andaman & Nicobar Islands" },
  { code: "37", name: "Andhra Pradesh" },
  { code: "12", name: "Arunachal Pradesh" },
  { code: "18", name: "Assam" },
  { code: "10", name: "Bihar" },
  { code: "04", name: "Chandigarh" },
  { code: "22", name: "Chhattisgarh" },
  { code: "26", name: "Dadra & Nagar Haveli" },
  { code: "25", name: "Daman & Diu" },
  { code: "07", name: "Delhi" },
  { code: "30", name: "Goa" },
  { code: "24", name: "Gujarat" },
  { code: "06", name: "Haryana" },
  { code: "02", name: "Himachal Pradesh" },
  { code: "01", name: "Jammu & Kashmir" },
  { code: "20", name: "Jharkhand" },
  { code: "29", name: "Karnataka" },
  { code: "32", name: "Kerala" },
  { code: "38", name: "Ladakh" },
  { code: "31", name: "Lakshadweep" },
  { code: "23", name: "Madhya Pradesh" },
  { code: "27", name: "Maharashtra" },
  { code: "14", name: "Manipur" },
  { code: "17", name: "Meghalaya" },
  { code: "15", name: "Mizoram" },
  { code: "13", name: "Nagaland" },
  { code: "21", name: "Odisha" },
  { code: "34", name: "Puducherry" },
  { code: "03", name: "Punjab" },
  { code: "08", name: "Rajasthan" },
  { code: "11", name: "Sikkim" },
  { code: "33", name: "Tamil Nadu" },
  { code: "36", name: "Telangana" },
  { code: "16", name: "Tripura" },
  { code: "09", name: "Uttar Pradesh" },
  { code: "05", name: "Uttarakhand" },
  { code: "19", name: "West Bengal" },
  { code: "97", name: "Other Territory" },
];

/* ── Major cities keyed by GST state code ── */
const INDIA_CITIES = {
  "35": ["Port Blair"],
  "37": ["Visakhapatnam", "Vijayawada", "Guntur", "Nellore", "Kurnool", "Tirupati",
          "Rajahmundry", "Kakinada", "Eluru", "Ongole", "Anantapur", "Kadapa"],
  "12": ["Itanagar", "Naharlagun", "Pasighat", "Tawang", "Ziro"],
  "18": ["Guwahati", "Silchar", "Dibrugarh", "Jorhat", "Nagaon", "Tinsukia",
          "Tezpur", "Bongaigaon", "Dhubri", "Goalpara"],
  "10": ["Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Purnia", "Darbhanga",
          "Bihar Sharif", "Arrah", "Begusarai", "Katihar", "Saharsa", "Chapra"],
  "04": ["Chandigarh"],
  "22": ["Raipur", "Bhilai", "Korba", "Bilaspur", "Durg", "Raigarh",
          "Jagdalpur", "Rajnandgaon", "Ambikapur"],
  "26": ["Silvassa"],
  "25": ["Daman", "Diu"],
  "07": ["New Delhi", "Dwarka", "Rohini", "Janakpuri", "Lajpat Nagar",
          "Connaught Place", "Karol Bagh", "Saket", "Pitampura", "Preet Vihar",
          "Nehru Place", "Laxmi Nagar", "Mayur Vihar"],
  "30": ["Panaji", "Margao", "Vasco da Gama", "Mapusa", "Ponda", "Calangute"],
  "24": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar", "Jamnagar",
          "Junagadh", "Gandhinagar", "Anand", "Mehsana", "Morbi", "Bharuch",
          "Navsari", "Valsad", "Amreli", "Botad", "Porbandar"],
  "06": ["Faridabad", "Gurgaon", "Panipat", "Ambala", "Yamunanagar", "Rohtak",
          "Hisar", "Karnal", "Sonipat", "Panchkula", "Rewari", "Sirsa", "Bhiwani"],
  "02": ["Shimla", "Mandi", "Dharamshala", "Solan", "Baddi", "Nahan",
          "Palampur", "Hamirpur", "Kullu", "Bilaspur"],
  "01": ["Srinagar", "Jammu", "Anantnag", "Sopore", "Baramulla",
          "Udhampur", "Kathua", "Rajouri", "Poonch"],
  "20": ["Ranchi", "Jamshedpur", "Dhanbad", "Bokaro", "Deoghar",
          "Hazaribagh", "Giridih", "Ramgarh", "Palamu", "Dumka"],
  "29": ["Bengaluru", "Mysuru", "Mangaluru", "Hubli", "Belagavi", "Davangere",
          "Ballari", "Vijayapura", "Tumkur", "Udupi", "Shivamogga", "Dharwad",
          "Gulbarga", "Hassan", "Bidar", "Raichur", "Chitradurga"],
  "32": ["Thiruvananthapuram", "Kochi", "Kozhikode", "Thrissur", "Kannur",
          "Kollam", "Palakkad", "Alappuzha", "Malappuram", "Ernakulam",
          "Kottayam", "Idukki", "Kasaragod", "Pathanamthitta"],
  "38": ["Leh", "Kargil"],
  "31": ["Kavaratti"],
  "23": ["Bhopal", "Indore", "Jabalpur", "Gwalior", "Ujjain", "Sagar",
          "Dewas", "Satna", "Ratlam", "Rewa", "Murwara", "Singrauli",
          "Burhanpur", "Khandwa", "Bhind", "Morena", "Chhindwara"],
  "27": ["Mumbai", "Pune", "Nagpur", "Nashik", "Thane", "Aurangabad",
          "Solapur", "Kolhapur", "Navi Mumbai", "Pimpri-Chinchwad",
          "Amravati", "Akola", "Latur", "Sangli", "Jalgaon", "Dhule",
          "Nanded", "Chandrapur", "Bhusawal", "Ahmednagar"],
  "14": ["Imphal", "Thoubal", "Bishnupur", "Churachandpur"],
  "17": ["Shillong", "Tura", "Nongstoin", "Jowai"],
  "15": ["Aizawl", "Lunglei", "Champhai", "Serchhip"],
  "13": ["Kohima", "Dimapur", "Mokokchung", "Tuensang", "Wokha"],
  "21": ["Bhubaneswar", "Cuttack", "Rourkela", "Brahmapur", "Sambalpur",
          "Puri", "Balasore", "Baripada", "Bhadrak", "Jharsuguda", "Angul", "Kendujhar"],
  "34": ["Puducherry", "Karaikal", "Yanam"],
  "03": ["Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Bathinda",
          "Mohali", "Pathankot", "Hoshiarpur", "Moga", "Firozpur",
          "Kapurthala", "Ropar", "Faridkot", "Sangrur"],
  "08": ["Jaipur", "Jodhpur", "Kota", "Bikaner", "Ajmer", "Udaipur",
          "Bhilwara", "Alwar", "Sikar", "Sri Ganganagar", "Barmer",
          "Pali", "Tonk", "Churu", "Nagaur", "Jhunjhunu", "Bundi"],
  "11": ["Gangtok", "Namchi", "Gyalshing", "Mangan"],
  "33": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem",
          "Tiruppur", "Vellore", "Erode", "Thoothukudi", "Dindigul",
          "Thanjavur", "Tirunelveli", "Hosur", "Nagercoil", "Kumbakonam",
          "Kanchipuram", "Cuddalore", "Karur", "Sivakasi", "Pollachi"],
  "36": ["Hyderabad", "Warangal", "Nizamabad", "Karimnagar", "Khammam",
          "Mahbubnagar", "Nalgonda", "Adilabad", "Suryapet", "Siddipet",
          "Ramagundam", "Sangareddy"],
  "16": ["Agartala", "Udaipur", "Dharmanagar", "Belonia", "Kailashahar"],
  "09": ["Lucknow", "Kanpur", "Agra", "Varanasi", "Meerut", "Prayagraj",
          "Ghaziabad", "Noida", "Bareilly", "Aligarh", "Moradabad",
          "Gorakhpur", "Mathura", "Firozabad", "Jhansi", "Saharanpur",
          "Muzaffarnagar", "Hapur", "Rampur", "Shahjahanpur", "Faizabad"],
  "05": ["Dehradun", "Haridwar", "Roorkee", "Haldwani", "Kashipur",
          "Rishikesh", "Rudrapur", "Nainital", "Mussoorie", "Kotdwar"],
  "19": ["Kolkata", "Asansol", "Siliguri", "Durgapur", "Bardhaman",
          "Malda", "Baharampur", "Habra", "Kharagpur", "Shantipur",
          "Darjeeling", "Jalpaiguri", "Haldia", "Cooch Behar", "Howrah",
          "Hooghly", "Purulia", "Bankura", "Krishnanagar"],
};

/* Flat sorted list for when no state is selected yet */
const ALL_INDIA_CITIES = [...new Set(Object.values(INDIA_CITIES).flat())].sort();

/* ── Country list (India first, rest alphabetical) ── */
const WORLD_COUNTRIES = [
  "India",
  "Afghanistan", "Australia", "Austria", "Bahrain", "Bangladesh", "Belgium",
  "Bhutan", "Brazil", "Canada", "China", "Cyprus", "Denmark", "Egypt",
  "Ethiopia", "Finland", "France", "Germany", "Ghana", "Greece",
  "Hong Kong", "Hungary", "Indonesia", "Iran", "Iraq", "Ireland",
  "Israel", "Italy", "Japan", "Jordan", "Kazakhstan", "Kenya",
  "Kuwait", "Malaysia", "Maldives", "Malta", "Mauritius", "Mexico",
  "Morocco", "Myanmar", "Nepal", "Netherlands", "New Zealand", "Nigeria",
  "Norway", "Oman", "Pakistan", "Philippines", "Poland", "Portugal",
  "Qatar", "Romania", "Russia", "Saudi Arabia", "Singapore", "South Africa",
  "South Korea", "Spain", "Sri Lanka", "Sweden", "Switzerland",
  "Taiwan", "Tanzania", "Thailand", "Turkey", "Uganda",
  "United Arab Emirates", "United Kingdom", "United States",
  "Vietnam", "Zambia", "Zimbabwe",
];

/* ============================================================
   Alpine.js component factory
   Usage:  x-data="indiaForm({ gstin, state, code, city, country })"
   ============================================================ */
function indiaForm(opts) {
  return {
    /* Current field values (bound via x-model) */
    gstin:       opts.gstin   || "",
    stateVal:    opts.state   || "",
    codeVal:     opts.code    || "",
    cityVal:     opts.city    || "",
    countryVal:  opts.country || "India",

    /* Dropdown open flags */
    stateOpen:   false,
    codeOpen:    false,
    cityOpen:    false,
    countryOpen: false,

    /* ── Filtered lists (recomputed reactively) ── */
    get stateFiltered() {
      const q = this.stateVal.toLowerCase().trim();
      const list = q
        ? INDIA_STATES.filter(s => s.name.toLowerCase().includes(q))
        : INDIA_STATES;
      return list.slice(0, 12);
    },

    get codeFiltered() {
      const q = this.codeVal.trim();
      const list = q
        ? INDIA_STATES.filter(s =>
            s.code.startsWith(q) ||
            s.name.toLowerCase().includes(q.toLowerCase()))
        : INDIA_STATES;
      return list.slice(0, 12);
    },

    get cityFiltered() {
      const state = INDIA_STATES.find(s => s.name === this.stateVal);
      const pool  = state ? (INDIA_CITIES[state.code] || []) : ALL_INDIA_CITIES;
      const q     = this.cityVal.toLowerCase().trim();
      const list  = q ? pool.filter(c => c.toLowerCase().includes(q)) : pool;
      return list.slice(0, 12);
    },

    get countryFiltered() {
      const q = this.countryVal.toLowerCase().trim();
      const list = q
        ? WORLD_COUNTRIES.filter(c => c.toLowerCase().includes(q))
        : WORLD_COUNTRIES;
      return list.slice(0, 12);
    },

    /* ── Pick handlers ── */
    pickState(s)   { this.stateVal = s.name; this.codeVal  = s.code; this.stateOpen = false; this.codeOpen = false; },
    pickCode(s)    { this.stateVal = s.name; this.codeVal  = s.code; this.codeOpen  = false; this.stateOpen = false; },
    pickCity(c)    { this.cityVal    = c; this.cityOpen    = false; },
    pickCountry(c) { this.countryVal = c; this.countryOpen = false; },

    /* ── GSTIN auto-fill: state + code + PAN ── */
    onGstinChange() {
      const g = this.gstin || "";
      if (g.length === 15) {
        const code  = g.slice(0, 2);
        const pan   = g.slice(2, 12);
        const state = INDIA_STATES.find(s => s.code === code);
        if (state) {
          this.stateVal = state.name;
          this.codeVal  = state.code;
        }
        const panEl = document.getElementById("id_pan");
        if (panEl) panEl.value = pan;
      }
    },
  };
}

/* Variant for the company profile settings form (extra logo/sig preview) */
function indiaProfileForm(opts) {
  return indiaForm(opts);
}

/* ============================================================
   customerForm()
   Used on the Customer create/edit form.
   Handles billing + shipping address comboboxes + GSTIN fill.
   ============================================================ */
function customerForm(opts) {
  return {
    gstin: opts.gstin || '',
    sameAsBilling: opts.sameAsBilling !== false,

    /* ── Billing ── */
    billingStateVal:   opts.billingState   || '',
    billingCodeVal:    opts.billingCode    || '',
    billingCityVal:    opts.billingCity    || '',
    billingCountryVal: opts.billingCountry || 'India',
    billingStateOpen:   false,
    billingCodeOpen:    false,
    billingCityOpen:    false,
    billingCountryOpen: false,

    /* ── Shipping ── */
    shippingStateVal:   opts.shippingState   || '',
    shippingCodeVal:    opts.shippingCode    || '',
    shippingCityVal:    opts.shippingCity    || '',
    shippingCountryVal: opts.shippingCountry || 'India',
    shippingStateOpen:   false,
    shippingCodeOpen:    false,
    shippingCityOpen:    false,
    shippingCountryOpen: false,

    /* ── GSTIN auto-fill (fills billing state + code + PAN) ── */
    onGstinChange() {
      const g = this.gstin || '';
      if (g.length === 15) {
        const code  = g.slice(0, 2);
        const pan   = g.slice(2, 12);
        const state = INDIA_STATES.find(s => s.code === code);
        if (state) {
          this.billingStateVal = state.name;
          this.billingCodeVal  = state.code;
        }
        const panEl = document.getElementById('id_pan');
        if (panEl) panEl.value = pan;
      }
    },

    /* ── Billing filtered lists ── */
    get billingStateFiltered() {
      const q = this.billingStateVal.toLowerCase().trim();
      return (q ? INDIA_STATES.filter(s => s.name.toLowerCase().includes(q)) : INDIA_STATES).slice(0, 12);
    },
    get billingCodeFiltered() {
      const q = this.billingCodeVal.trim();
      return (q ? INDIA_STATES.filter(s => s.code.startsWith(q) || s.name.toLowerCase().includes(q.toLowerCase())) : INDIA_STATES).slice(0, 12);
    },
    get billingCityFiltered() {
      const st = INDIA_STATES.find(s => s.name === this.billingStateVal);
      const pool = st ? (INDIA_CITIES[st.code] || []) : ALL_INDIA_CITIES;
      const q = this.billingCityVal.toLowerCase().trim();
      return (q ? pool.filter(c => c.toLowerCase().includes(q)) : pool).slice(0, 12);
    },
    get billingCountryFiltered() {
      const q = this.billingCountryVal.toLowerCase().trim();
      return (q ? WORLD_COUNTRIES.filter(c => c.toLowerCase().includes(q)) : WORLD_COUNTRIES).slice(0, 12);
    },

    pickBillingState(s)   { this.billingStateVal = s.name; this.billingCodeVal = s.code; this.billingStateOpen = false; this.billingCodeOpen = false; },
    pickBillingCode(s)    { this.billingStateVal = s.name; this.billingCodeVal = s.code; this.billingCodeOpen = false; this.billingStateOpen = false; },
    pickBillingCity(c)    { this.billingCityVal    = c; this.billingCityOpen    = false; },
    pickBillingCountry(c) { this.billingCountryVal = c; this.billingCountryOpen = false; },

    /* ── Shipping filtered lists ── */
    get shippingStateFiltered() {
      const q = this.shippingStateVal.toLowerCase().trim();
      return (q ? INDIA_STATES.filter(s => s.name.toLowerCase().includes(q)) : INDIA_STATES).slice(0, 12);
    },
    get shippingCodeFiltered() {
      const q = this.shippingCodeVal.trim();
      return (q ? INDIA_STATES.filter(s => s.code.startsWith(q) || s.name.toLowerCase().includes(q.toLowerCase())) : INDIA_STATES).slice(0, 12);
    },
    get shippingCityFiltered() {
      const st = INDIA_STATES.find(s => s.name === this.shippingStateVal);
      const pool = st ? (INDIA_CITIES[st.code] || []) : ALL_INDIA_CITIES;
      const q = this.shippingCityVal.toLowerCase().trim();
      return (q ? pool.filter(c => c.toLowerCase().includes(q)) : pool).slice(0, 12);
    },
    get shippingCountryFiltered() {
      const q = this.shippingCountryVal.toLowerCase().trim();
      return (q ? WORLD_COUNTRIES.filter(c => c.toLowerCase().includes(q)) : WORLD_COUNTRIES).slice(0, 12);
    },

    pickShippingState(s)   { this.shippingStateVal = s.name; this.shippingCodeVal = s.code; this.shippingStateOpen = false; this.shippingCodeOpen = false; },
    pickShippingCode(s)    { this.shippingStateVal = s.name; this.shippingCodeVal = s.code; this.shippingCodeOpen = false; this.shippingStateOpen = false; },
    pickShippingCity(c)    { this.shippingCityVal    = c; this.shippingCityOpen    = false; },
    pickShippingCountry(c) { this.shippingCountryVal = c; this.shippingCountryOpen = false; },
  };
}
