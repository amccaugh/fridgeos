const zmq = require("zeromq")
const sqlite3 = require('better-sqlite3');
const load_cal = require('./load_cal_only.js') 
const fetch = (...args) => import('node-fetch').then(({default: fetch}) => fetch(...args));
const heater_server = 'http://132.163.53.82:3300'


var db = sqlite3('log.db');

var sensor_dict;
// retrieve all sensors (compressor + diodes)

function fetch_sensors(table) {    
  var stmt = db.prepare(`select * from ${table}`);
  stmt.raw(true);
  var results = stmt.all()
  // console.log('stmt', stmt);
  let sensor_dict = {}
  for (elt of results) {
    // console.log('elt', elt);
    sensor_dict[elt[1]] = {}
    sensor_dict[elt[1]]['id'] = elt[0];
    sensor_dict[elt[1]]['cal_file'] = elt[3];
  }
  return sensor_dict;
}

sensor_dict = {...sensor_dict, ...fetch_sensors('compressor_list')};
sensor_dict = {...sensor_dict, ...fetch_sensors('diode_list')};
sensor_dict = {...sensor_dict, ...fetch_sensors('heaters_list')};
sensor_dict = {...sensor_dict, ...fetch_sensors('lockins_list')};
// console.log(sensor_dict);

// const create = 'CREATE TABLE IF NOT EXISTS data ( TS INT, ID INT , READING REAL);'
// results = db.exec(create);
// console.log(results);
// var insert = db.prepare(`INSERT INTO data VALUES (?, ?, ?);`);
// var stmt;
async function convertMsg(msg, sensor_dict) { 
  let data = JSON.parse(msg.toString());
  var print_time = true;
  //Object.keys(data).forEach( (element) => {
  var converted = Object.keys(data).map( (element) => {
    // Look at each key to data, and try to figure out if it is valid
    //   key in the sensor_dict
    let idx = Object.keys(sensor_dict).find( (elt) => {
      return element.toUpperCase() == elt.toUpperCase();
    });
    if (idx === undefined) {  // handle case where the key in the data is not in the db
      if (element != 'TIME') {
        // if (print_time) console.log((new Date()).toLocaleString());
        // console.log(`     >>> "${element}" <<< not found in the database, value: ${data[element]}`);
        print_time = false;
      }
    } else {
      // console.log('found idx', idx, element, data.TIME, sensor_dict[idx]['id'], data[element]);
      var TS = data.TIME;
      var ID = sensor_dict[idx]['id'];
      var RAW = data[element];
      // stmt = db.prepare(insert);
      // stmt.run(TS, ID, RAW);
      let cal_name = sensor_dict[idx]['cal_file'];
      let value = cal[cal_name](RAW);
      value = Array.isArray(value) ? value[0] : value
      value = Number(value.toFixed(2));
      if (false) { 
        console.log(ID, ('                    '+element).slice(-20),
          ('        '+cal_name).slice(-10),
          ('        '+RAW.toFixed(2).toString()).slice(-8),
          ('        '+value.toString()).slice(-8)
        );
      }
      // return [TS, ID, RAW];
      return [TS, ID, element, cal_name, Number(RAW.toFixed(2)), value];
    }
  });
  // console.log(array);
  // filter out when key was not found in the log database
  converted = converted.filter( elt => elt!==undefined);
  return converted;
}

async function setLPH(ch, current) {
  console.log('setLPH');
  var url = `http://132.163.53.82:3300/lph/${ch}/set/current?i=${current}`;
  console.log(url);
  var r = await fetch(url);
  var response = await r.json();
  console.log('response', response);
}
var nameToNumber = {}
// async function setHeaterIfNeeded(name, ch, T, target=45, margin=0.1, minSet=2, maxSet=3) {
async function setHeaterIfNeeded(name, T, target=45, margin=0.1, minSet=2, maxSet=3) {
  // Need global nameToNumber to be already set up.
  var url, r, response;
  let ch = nameToNumber[name.toUpperCase()+'_HEATER'].ch;
  console.log('        setHeaterIfNeeded', name, ch, T, target, margin, minSet, maxSet);
  console.log('T-target', T-target);
  if (target==0) {
    //set current to zero
    console.log('set current to 0');
    url = `http://132.163.53.82:3300/hph/${ch}/set/current?i=0`
    r = await fetch(url);
    response = await r.json();
    console.log(`        response hph${ch} set`, response);
    // disable 
  } else if ((target-T) > 3) {
    url = `http://132.163.53.82:3300/hph/${ch}/get/current`
    console.log('        ', url);
    r = await fetch(url);
    response = await r.json();
    console.log(`        response hph${ch} get`, response);
    url = `http://132.163.53.82:3300/hph/${ch}/set/current?i=20`
    r = await fetch(url);
    response = await r.json();
    console.log(`        response hph${ch} set`, response);
  } else if ((T-target) > 1) {
    console.log('set current to 0');
    url = `http://132.163.53.82:3300/hph/${ch}/set/current?i=0`
    r = await fetch(url);
    response = await r.json();
    console.log(`        response hph${ch} set`, response);
  } else if (T< (target-margin)) {
    url = `http://132.163.53.82:3300/hph/${ch}/get/current`
    console.log('        ', url);
    r = await fetch(url);
    response = await r.json();
    console.log(`        response hph${ch} get`, response);
    if (response < maxSet) {
      url = `http://132.163.53.82:3300/hph/${ch}/set/current?i=${response+1}`
      r = await fetch(url);
      response = await r.json();
      console.log(`        response hph${ch} set`, response);
    } else if (response > maxSet) {
      url = `http://132.163.53.82:3300/hph/${ch}/set/current?i=${maxSet}`
      r = await fetch(url);
      response = await r.json();
      console.log(`        response hph${ch} set`, response);
    } else console.log(`        hph ${ch} should already be set to max, ${maxSet}`);
  } else if (T>(target+margin)) {
    url = `http://132.163.53.82:3300/hph/${ch}/get/current`
    console.log('        ',url);
    r = await fetch(url);
    response = await r.json();
    console.log(`         response hph${ch} get`, response);
    if (response > minSet) {
      url = `http://132.163.53.82:3300/hph/${ch}/set/current?i=${response-1}`
      r = await fetch(url);
      response = await r.json();
      console.log(`        response hph${ch} set`, response);
    } else if(response<minSet) {
      url = `http://132.163.53.82:3300/hph/${ch}/set/current?i=${minSet}`
      r = await fetch(url);
      response = await r.json();
      console.log(`        response hph${ch} set`, response);
    }
    else console.log(`        hph ${ch} should already be set to min: ${minSet}`);
  }
}
function lookup(name, converted_readings) {
  // console.log('trying to lookup');
  let result = converted_readings.find( e => e[2].toUpperCase() == name.toUpperCase() );
  if (result !== undefined) {
    // console.log('        ',result[4], result[5], typeof(result[4]), typeof(result[5]))
    return result[5];
  } else {
    console.log('        ', name, 'not found in message');
    return null
  }
}

async function turnOffPumpHeater(pumpNames, converted_readings) {
  //pumpNames is an array of pump thermometer names
  for (name of pumpNames) {
    console.log(name, lookup(name, converted_readings));
    T = lookup(name, converted_readings);
    await setHeaterIfNeeded(name, T, 0, 0.1, 1, 2);
  }
}
async function regulateHotPumps(pumpNames, converted_readings) {
  //  Regulate pumps around 45K
  var T;
  for (name of pumpNames) {
    console.log(name, lookup(name, converted_readings));
    T = lookup(name, converted_readings);
    if (name == '4pumpA') 
      await setHeaterIfNeeded(name, T, 45, 0.1, 1, 10);
    if (name == '3pumpA')
      await setHeaterIfNeeded(name, T, 45, 0.1, 2, 5);
      // await setHeaterIfNeeded(name, T, 45, 0.1, 2, 3);
    if (name == '4pumpB')
      await setHeaterIfNeeded(name, T, 45, 0.1, 0, 7);
    if (name == '3pumpB')
      await setHeaterIfNeeded(name, T, 45, 0.1, 2, 5);
      // await setHeaterIfNeeded(name, T, 45, 0.1, 2, 3);
  }
}

async function checkOtherCycle(other_id, converted_readings) {
  let testnames = buildNames('34',other_id, 'head')
  var cold = true;
  for (name of testnames) {
    var T = lookup(name, converted_readings);
    let thresh = 4;
    cold = cold && (T<thresh);
    console.log (name, T, T<thresh, cold);
  }
  if (!cold) {
    let testnames = buildNames('34',[other_id+'_HEATER'], 'SWITCH')
    console.log(testnames);
    let setting;
    for (name of testnames) {
      let ch = nameToNumber[name].ch
      setting = lookup(name, converted_readings);
      console.log(name, ch, setting);
      if (setting != 0) await setLPH(ch, 0);
      else console.log(name, 'is already off');
    }
  }
}


function buildNames(pre, post, middle) {
    var ret=[];
    for (prefix of pre) {
        for (suffix of post) {
          let name = prefix + middle + suffix
          // if (!ret) ret = [];
          ret.push(name) 
          // console.log(name)
          // console.log(ret);
        }
    }
  return ret;
}
console.log('try buildnames');
let testnames = buildNames('43', 'AB', 'head');
console.log(testnames);
function textTable(converted_readings) {
  for (name of ['4pumpA', '4pumpB', '3pumpA', '3pumpB', '4K', '4switchA', '3switchA', '4PUMPA_HEATER_I','3PUMPA_HEATER_I']) {
    T = lookup(name, converted_readings);
    console.log(name, T);
  }
}

async function run() {
  console.log('loading calibration tables');
  cal = await load_cal.load_calibrations('132.163.53.82:3200');
  console.log(cal);
  //setup dictionary keyed with pumpName and values of heatername and ch number
  // var nameToNumber = {}
  let offset = 0
  for (heater of ['hph', 'lph']) {
    if (heater=='lph') offset = 1
    for (let i=0; i<4; i++) {
      let dac_setting = await fetch(`${heater_server}/${heater}/${i+offset}/get/current`);
      dac_setting = await dac_setting.json();
      // console.log(i, 'dac_setting', dac_setting);
      if (typeof(dac_setting)=='number') {  // handle response from hph
        // get heater name from monitor query 
        let command = `${heater_server}/hph/${i}/get/monitor`;
        let response = await fetch(command);
        response = await response.json()
        console.log('response',response);
        let name = Object.keys(response)[0];
        console.log(name, name.split('_HEATER')[0]);
        nameToNumber[name] = {
          name: name.split('_HEATER')[0],
          ch: i+offset
        }
      } else { // handle response from lph
        let name = Object.keys(dac_setting)[0];
        console.log(name, name.split('_HEATER')[0]);
        nameToNumber[name] = {
          name: name.split('_HEATER')[0],
          ch: i+offset
        }
      }
      console.log(i+offset, 'dac_setting', dac_setting);
    }
  }
  console.log(nameToNumber)

  const sock = new zmq.Subscriber

  sock.connect("tcp://127.0.0.1:3001")
  sock.subscribe("")
  console.log("Subscriber connected to port 3001")
  console.log('-'.padStart(79,'-'));
  var state_start_time = new Date();

  var enterStateTime = new Date();
  console.log('enterStateTime', enterStateTime);
  var elapsedTimeInState ;

  var state = {name: null, justEntered: true}
  state.name = 'ApumpsHot'
  state.name = 'turnoffpumpsA';
  state.name = 'turnOnHeatswitch4A' 
  state.name = 'turnOnHeatswitch3A' 
//  state.name = 'waitForPumpsToCool'
  state.name = 'turnOn4Heatswitches'

  function setState(name, justEntered=false) {
    // set global variable state
    state.name = name;
    state.justEntered = justEntered;
  }
  function checkIfInState(name) {
    return state.name == name
  }
  function check_justEntered() {
    if (state.justEntered) {
      state.justEntered = false
      enterStateTime = new Date();
      console.trace()
      console.log('enterStateTime', enterStateTime);
      return true
    } else return false
  }
  async function getXpumpsHot(cycle_id) {
    let justEntered = check_justEntered()
    await regulateHotPumps(['4pump'+cycle_id], converted_readings);
    if (lookup('3switch'+cycle_id, converted_readings) < 12)
      await regulateHotPumps(['3pump'+cycle_id], converted_readings);

    testnames = buildNames('34', cycle_id, 'pump')
    let pass = true;
    for (name of testnames) {
      T = lookup(name, converted_readings);
      let target = 45
      let margin = 0.25
      let good = (T > (target-margin)) && (T<(target+margin))
      pass = pass && good
      console.log (name, T, pass);
    }

    targets = [6, 4];
    testnames = buildNames('34',cycle_id, 'head');
    console.log(testnames);
    let idx = 0
    let cold = pass;
    for (name of testnames) {
      T = lookup(name, converted_readings);
      let thresh = targets[idx]
      cold = cold && T < thresh && (T!==null);
      console.log (name, T, thresh, T<thresh, (T!==null), cold);
      idx += 1
    }
    return cold
  }

  async function turnoffXpumps(cycle_id) {
    let justEntered = check_justEntered()
    console.log(justEntered);
    if (justEntered) {
      await turnOffPumpHeater(['4PUMP'+cycle_id, '3PUMP'+cycle_id ], converted_readings);
    }
  }

  // setState('waitForHeatswitchesToCool', true);
  // setState('turnOn4Heatswitches', true)
  // setState('turnOnAllPumps', true)
  // setState('turnOn3Heatswitches', true)
  // setState('startCycleA', true)
  // setState('turnOnHeatswitch4A', true)
  //  setState('turnOnHeatswitch4B', true)
  // setState('turnOnHeatswitch3A', true)
  // setState('getPumpsHotA', true)
  setState('getPumpsHotB', true)
  // setState('turnoffpumpsA', true)
  // setState('startCycleB', true)
  // setState('getPumpsWarmB', true)
  // setState('turnoffpumpsB', true)
  // setState('turnOnHeatswitch4B', true)
  // setState('turnOnHeatswitch3B', true)

  for await (const [topic, msg] of sock) {
    // console.log("received a message related to:", topic.toString(), "containing message:", msg); //, msg.toString())

    var converted_readings = await convertMsg(msg, sensor_dict);
    console.log((new Date()).toLocaleString());

    console.log('current state:', state);
    //if (checkIfInState('waitForHeatswitchesToCool')) {
    var justEntered;
    var cold = false;
    // var cycle_id='C';
    // var other_id='D';
    switch(state.name) {
      case 'waitForHeatswitchesToCool': {
        console.log('check if first time', check_justEntered())
        let now = new Date();
        console.log(now, enterStateTime);
        elapsedTimeInState = now - enterStateTime;
        console.log(`time spent in ${state.name}:`, elapsedTimeInState/1000);
        cold = true;
        for (name of ['4switchA' , '3switchA', '4switchB', '3switchB']) {
          var T = lookup(name, converted_readings);
          let thresh = 12;
          cold = cold && (T<thresh);
          console.log (name, T, T<thresh, cold);
        }
        if (cold) {
          setState('turnOnAllPumps', true)
          enterStateTime = new Date();
        }
        elapsedTimeInState = new Date() - enterStateTime;
        break;
      }
      case 'turnOnAllPumps': {
        justEntered = check_justEntered()

        await regulateHotPumps(['4pumpA'], converted_readings);
        await regulateHotPumps(['3pumpA'], converted_readings);
        await regulateHotPumps(['4pumpB'], converted_readings);
        await regulateHotPumps(['3pumpB'], converted_readings);
        elapsedTimeInState = new Date() - enterStateTime;
        console.log(`time spent in ${state.name}:`,
          elapsedTimeInState/1000);

        let testnames = buildNames('43', 'AB', 'head');
        cold = true;
        for (name of testnames) {
          var T = lookup(name, converted_readings);
          let thresh = 4.1;
          cold = cold && (T<thresh) && (T!==null);
          console.log (name, T, T<thresh, T!==null, cold);
        }
        if (cold) {
          console.log('all heads below 4K')
          setState('turnOn4Heatswitches', true)
        }
        break;
      }
      case 'turnOn4Heatswitches': {
        justEntered = check_justEntered()
        if (justEntered) {
          console.log('just entered state', state);
          enterStateTime = new Date();
          await turnOffPumpHeater(['4PUMPA', '4pumpB' ], converted_readings);
        } 
        low = true;
        if (!justEntered) {
          let testnames = buildNames('4',['A_HEATER_I', 'B_HEATER_I'], 'PUMP')
          cold = true;
          for (name of testnames) {
            var T = lookup(name, converted_readings);
            let thresh = 0.1;
            cold = cold && (T<thresh);
            console.log (name, T, T<thresh, cold);
          }
          console.log('ready to turn on heatswitches');
          await setLPH(1, 231);
          await setLPH(3, 231);
        }
        await regulateHotPumps(['3pumpA'], converted_readings);
        await regulateHotPumps(['3pumpB'], converted_readings);

        elapsedTimeInState = new Date() - enterStateTime;
        console.log('elapsedTimeInState:', elapsedTimeInState);
        if (elapsedTimeInState > 20*60*1000) {
          console.log('time to turn on 3Heatswitches');
          setState('turnOn3Heatswitches', true)
        }
        break;
      }
      case 'turnOn3Heatswitches': {
        justEntered = check_justEntered()
        if (justEntered) {
          console.log('just entered state', state);
          enterStateTime = new Date();
          let testnames = buildNames('3','AB','PUMP');
          await turnOffPumpHeater(testnames, converted_readings);
        } 
        low = true;
        if (!justEntered) {
          let testnames = buildNames('3',['A_HEATER_I', 'B_HEATER_I'], 'PUMP')
          var low = true;
          for (name of testnames) {
            var I = lookup(name, converted_readings);
            let thresh = 0.1;
            low = low && (I<thresh);
            console.log (name, I, I<thresh, low);
          }
          console.log('ready to turn on heatswitches');
          testnames = buildNames('3',['A_HEATER', 'B_HEATER'], 'SWITCH')
          let setting;
          for (name of testnames) {
            let ch = nameToNumber[name].ch
            setting = lookup(name, converted_readings);
            console.log(name, ch, setting);
            if (setting != 231) await setLPH(ch, 231);
            else console.log(name, 'is already on');
          }
        }

        elapsedTimeInState = new Date() - enterStateTime;
        console.log('elapsedTimeInState:', elapsedTimeInState);
        // *********************
        // FIXME:  elapsedTimeInState
        // *********************
        if (elapsedTimeInState > 30*60*1000) {
          console.log('time to start cycle');
          setState('startCycleA', true)
        }
        break;
      }
      case 'startCycleA': { 
        // Turn off heatswitches for A and wait for them to cool.
        justEntered = check_justEntered()
        let cycle_id = state.name[state.name.length -1]
        // let cycle_id = 'A'
        if (justEntered) {
          let testnames = buildNames('34',[cycle_id+'_HEATER'], 'SWITCH')
          console.log(testnames);
          let setting;
          for (name of testnames) {
            let ch = nameToNumber[name].ch
            setting = lookup(name, converted_readings);
            console.log(name, ch, setting);
            if (setting != 0) await setLPH(ch, 0);
            else console.log(name, 'is already off');
          }
        }
        // check that things got set to 0
        testnames = buildNames('34',[cycle_id+'_HEATER'], 'SWITCH')
        cold = true;
        let setting;
        for (name of testnames) {
          let ch = nameToNumber[name].ch
          setting = lookup(name, converted_readings);
          console.log(name, ch, setting);
          cold = cold && (setting==0)
          if (setting != 0) await setLPH(ch, 0);
          else console.log(name, 'is already off');
        }
        testnames = buildNames('43',cycle_id, 'switch')
        for (name of testnames) {
          var T = lookup(name, converted_readings);
          let thresh = 12;
          cold = cold && (T<thresh);
          console.log (name, T, T<thresh, cold);
        }
        if (cold) {
          setState('getPumpsWarm'+cycle_id, true)
        }
        break;
      }
      case 'getPumpsHotA': {
        justEntered = check_justEntered()
        let cycle_id = state.name[state.name.length -1]
        // let cycle_id = 'A'
        let cold = await getXpumpsHot(cycle_id);
        let timeToWait = 30*60*1000 - elapsedTimeInState

        if (cold) {
          elapsedTimeInState = new Date() - enterStateTime;
          // go to next state
          if (timeToWait<0) {
            console.log('go to next state');
            setState('turnoffpumps'+cycle_id, true)
          } else {
            console.log('Still need to wait', timeToWait/1000, 'seconds'); 
          }
        } else {
          console.log('Still need to wait', timeToWait/1000, 'seconds'); 
        }

        break;
      }
      case 'turnoffpumpsA': {
        // let justEntered = check_justEntered()  // already done in turnoffXpumps
        let cycle_id = state.name[state.name.length -1]
        // let cycle_id = 'A'
        await turnOffPumpHeater(['4PUMP'+cycle_id], converted_readings);
        // await turnoffXpumps(cycle_id);
        let other_id = (cycle_id=='A') ? 'B':'A';
        // await checkOtherCycle(other_id, converted_readings)
        elapsedTimeInState = new Date() - enterStateTime;
        if (elapsedTimeInState > 30*1000) {
          // wait 30 seconds then turn on heatswitches for cycle A
          setState('turnOnHeatswitch4'+cycle_id, true);
        }
        break;
      }
      case 'turnOnHeatswitch4A': {
        let justEntered = check_justEntered()
        let cycle_id = state.name[state.name.length -1]
        // let cycle_id = 'A'
        let ch = nameToNumber['4SWITCH'+cycle_id+'_HEATER'].ch
        console.log('try to set LPH', ch);
        await setLPH(ch, 231);

        await regulateHotPumps(['3pump'+cycle_id], converted_readings);

        let cold = lookup('3headA', converted_readings) < 6

        elapsedTimeInState = new Date() - enterStateTime;
        cold = cold && ( (lookup('4headA', converted_readings) < 1.0) || (elapsedTimeInState > (40*60*1000))) 

        if (cold) {
          setState('turnOnHeatswitch3A', true);
        }
        break;
      }
      case 'turnOnHeatswitch3A': {
        let justEntered = check_justEntered()
        // console.log('cycle_id', cycle_id);
        let cycle_id = state.name[state.name.length -1]
        // let cycle_id = 'A'
        if (justEntered) {
          await turnOffPumpHeater(['3PUMP'+cycle_id], converted_readings);
        }
        let ch = nameToNumber['3SWITCH'+cycle_id+'_HEATER'].ch
        console.log('try to set LPH', ch);
        // await setLPH(ch, 231);
        await setLPH(ch, 190);
        let other_id = (cycle_id=='A') ? 'B':'A';
        // await checkOtherCycle(other_id, converted_readings)
        elapsedTimeInState = new Date() - enterStateTime;
        // let timeToWait = 30*60*1000 - elapsedTimeInState
        let timeToWait = 10*60*1000 - elapsedTimeInState
        if (timeToWait<0) {
          console.log('go to next state');
          setState('startCycle'+other_id, true);
          enterStateTime = new Date();
        } else {
          console.log('Still need to wait', timeToWait/1000, 'seconds'); 
        }
        break;
      }
      case 'startCycleB': {
        // make sure heatswitches for B are off nd wait for them to cool.
        let cycle_id = state.name[state.name.length -1]
        console.log('extracted cycle_id', cycle_id);
        let justEntered = check_justEntered()
        if (justEntered) {
          let testnames = buildNames('34',['B_HEATER'], 'SWITCH')
          console.log(testnames);
          let setting;
          for (name of testnames) {
            let ch = nameToNumber[name].ch
            setting = lookup(name, converted_readings);
            console.log(name, ch, setting);
            if (setting != 0) await setLPH(ch, 0);
            else console.log(name, 'is already off');
          }
        }
        cold = true;
        testnames = buildNames('43','B', 'switch')
        for (name of testnames) {
          var T = lookup(name, converted_readings);
          let thresh = 12;
          cold = cold && (T<thresh);
          console.log (name, T, T<thresh, cold);
        }
        if (cold) {
          // setState('getPumpsHotB', true)
          setState('getPumpsWarmB', true)
        }
        break;
      }
      case 'getPumpsWarmA':
      case 'getPumpsWarmB': {
        let cycle_id = state.name[state.name.length -1]
        let justEntered = check_justEntered()
        let names = buildNames('43',cycle_id, 'PUMP')
        console.log(`${state.name} ${names}`);
        // let names = ['4pumpB', '3pumpB']
        var timeStep = 3*60*1000;
        for (name of names) {
          let ch = nameToNumber[name.toUpperCase()+'_HEATER'].ch;

          elapsedTimeInState = new Date() - enterStateTime;
          url = `http://132.163.53.82:3300/hph/${ch}/get/current`
          console.log('        ', url);
          r = await fetch(url);
          response = await r.json();
          console.log(`        response hph${ch} get`, response);
          let i = 3;
          if (elapsedTimeInState<timeStep) {
            // set heaters to 3
            i = 3;
          } else if (elapsedTimeInState<2*timeStep) {
            // set heaters to 6
            i = 6;
          } else if (elapsedTimeInState<3*timeStep) {
            // set heaters to 9
            i = 9;
          }
          // console.log(response, i);
          if (response != i) {
            url = `http://132.163.53.82:3300/hph/${ch}/set/current?i=${i}`
            r = await fetch(url);
            response = await r.json();
            console.log(`        response hph${ch} set`, response);
            url = `http://132.163.53.82:3300/hph/${ch}/get/current`
            console.log('        ', url);
            r = await fetch(url);
            response = await r.json();
            console.log(`        response hph${ch} get`, response);
          }
        }
        if (elapsedTimeInState>3*timeStep) {
          setState('getPumpsHot'+cycle_id)
        }
        break;
      }
      case 'getPumpsHotB': {
        let cycle_id = state.name[state.name.length -1]
        // let cycle_id = 'B'
        let cold = await getXpumpsHot(cycle_id);
        let timeToWait = 30*60*1000 - elapsedTimeInState

        if (cold) {
          elapsedTimeInState = new Date() - enterStateTime;
          // go to next state
          if (timeToWait<0) {
            console.log('go to next state');
            setState('turnoffpumps'+cycle_id, true)
          } else {
            console.log('Still need to wait', timeToWait/1000, 'seconds');
          }
        } else {
          console.log('Still need to wait', timeToWait/1000, 'seconds'); 
        }
        break;
      }
      case 'turnoffpumpsB': {
        let cycle_id = state.name[state.name.length -1]
        // let cycle_id = 'B'
        let other_id = (cycle_id=='A') ? 'B':'A';
        // await checkOtherCycle(other_id, converted_readings)
        // await turnoffXpumps(cycle_id);
        await turnOffPumpHeater(['4PUMP'+cycle_id], converted_readings);
        elapsedTimeInState = new Date() - enterStateTime;
        if (elapsedTimeInState > 30*1000) {
          // wait 30 seconds then turn on heatswitches for cycle A
          setState('turnOnHeatswitch4'+cycle_id, true);
        }
        break;
      }
      case 'turnOnHeatswitch4B': {
        justEntered = check_justEntered()
        let cycle_id = 'B'
        let ch = nameToNumber['4SWITCH'+cycle_id+'_HEATER'].ch
        console.log('try to set LPH', ch);
        // await setLPH(ch, 231);
        await setLPH(ch, 210);
        // console.log('try to set LPH');
        // await setLPH(3, 231);
        await regulateHotPumps(['3pump'+cycle_id], converted_readings);

        let cold = lookup('3head'+cycle_id, converted_readings) < 6

        elapsedTimeInState = new Date() - enterStateTime;
        let timeToWait = 40*60*1000 - elapsedTimeInState

        cold = cold && ( (lookup('4head'+cycle_id, converted_readings) < 1.0) || (timeToWait<0) )
        console.log('Still need to wait', timeToWait/1000, 'seconds'); 

        if (cold) {
          setState('turnOnHeatswitch3'+cycle_id, true);
        }
        break;
      }
      case 'turnOnHeatswitch3B': {
        let cycle_id = state.name[state.name.length -1]
        // let cycle_id = 'B'
        let justEntered = check_justEntered()
        if (justEntered) {
          await turnOffPumpHeater(['3PUMP'+cycle_id], converted_readings);
        }
        let ch = nameToNumber['3SWITCH'+cycle_id+'_HEATER'].ch
        console.log('try to set LPH', ch);
        // await setLPH(ch, 231);
        await setLPH(ch, 200);
        let other_id = (cycle_id=='A') ? 'B':'A';
        // await checkOtherCycle(other_id, converted_readings)
        elapsedTimeInState = new Date() - enterStateTime;
        let timeToWait = 10*60*1000 - elapsedTimeInState
        console.log('Still need to wait', timeToWait/1000, 'seconds'); 
        // if (elapsedTimeInState > 30*60*1000) {
        if (elapsedTimeInState > 0) {
          setState('startCycleA', true);
          enterStateTime = new Date();
        }
        break;
      }
      default: {
        console.log('unhandled state');
        break;
      }
    }
    textTable(converted_readings)
    console.log('enterStateTime', enterStateTime);
    elapsedTimeInState = new Date() - enterStateTime;
    console.log('elapsedTimeInState:', elapsedTimeInState);
    console.log('done processing:state:', state);
    console.log('-'.padStart(79,'-'));
  } 
}


run()


