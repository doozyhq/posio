var map = null,
  progressBar = null,
  markerGroup = null,
  socket = null,
  allowMultipleAnswer = false,
  playerNameStorage = "player_name",
  playerIdStorage = "player_id";

const gameId = window.location.pathname.split("/game/")[1];

if (!gameId) {
  window.location.href = "/";
}

var username = getUsername();
var userId = getSetUserId();

$(document).ready(function () {
  // Create the progress bar
  progressBar = new ProgressBar.Line("#progress", {
    color: "#FCB03C",
    duration: $("#progress").data("max-response-time") * 1000,
  });

  // Is user allowed answer multiple times to the same question
  allowMultipleAnswer = $("#game_rules").data("allow-multiple-answers");

  // Toggle top ten when user clicks on the leaderboard
  $("#leaderboard").click(function () {
    $("#top_ten").slideToggle();
    $("#user_rank").slideToggle();
  });

  $("#game_rules").click(() => {
    // Emit answer event
    socket.emit("play_again", gameId);
  });

  // Create the leaflet map
  map = createMap();

  // Create the marker group used to clear markers between turns
  markerGroup = new L.LayerGroup().addTo(map);

  // Look for a previously entered player name in local storage
  if (username && userId) {
    // If player name found, start the game using it
    joinGame(gameId, userId, username);
  } else {
    // Else, ask for player name
    login();
  }
});

const showLeaderboard = () => {
  $("#top_ten").slideToggle();
  $("#user_rank").slideToggle();
};

const hideLeaderboard = () => {
  $("#top_ten").slideToggle();
  $("#user_rank").slideToggle();
};

/**
 * Create the leaflet map.
 * @returns {Array|*}
 */
function createMap() {
  // How many zoom level are allowed
  var zoomLevel = $("#map").data("zoom-level");

  // Create a world map
  var map = L.map("map", {
    layers: [
      L.tileLayer(cdnUrl + "/tiles/{z}/{x}/{y}.png", {
        attribution:
          '<a href="https://github.com/abrenaut/posio" target="_blank">Posio</a> | Tiles by <a href="https://github.com/mapbox/tilemill" target="_blank">TileMill</a>',
        noWrap: true,
        ext: "png",
      }),
    ],
    zoomControl: zoomLevel != 0,
    zoom: 2,
    maxZoom: 2 + zoomLevel,
    minZoom: 2,
    center: [49, 2.5],
    // Force the user to stay between the given bounds
    maxBounds: [
      [-70.0, -180.0],
      [85.0, 180.0],
    ],
  });

  map.doubleClickZoom.disable();

  // Add a legend in the bottom left corner
  var legend = L.control({ position: "bottomleft" });

  legend.onAdd = function (map) {
    var div = L.DomUtil.create("div", "info");
    div.id = "legend";
    div.innerHTML +=
      '<div><img src="' +
      cdnUrl +
      "/images/marker-yours.svg" +
      '" alt="Your answer"/> Your answer</div>';
    div.innerHTML +=
      '<div><img src="' +
      cdnUrl +
      "/images/marker-correct.svg" +
      '" alt="Correct answer"/> Correct answer</div>';
    div.innerHTML +=
      '<div><img src="' +
      cdnUrl +
      "/images/marker-closest.svg" +
      '" alt="Best answer"/> Closest answer</div>';
    return div;
  };

  legend.addTo(map);

  return map;
}

/**
 * Ask the player for his name and store it in local storage if possible.
 * Once the player has entered a valid name, start the game.
 */
function login() {
  $("#modal_background").show();

  $("#login_form").submit(function (event) {
    event.preventDefault();

    var playerName = $("#player_name").val();

    // Validate player name
    if (!playerName) {
      $("#login_error").text("Please select a player name.");
    } else if (playerName.length > 50) {
      $("#login_error").text(
        "Player name must contain less than 50 characters."
      );
    } else {
      // Store player name if possible
      if (typeof Storage !== "undefined") {
        try {
          localStorage.setItem(playerNameStorage, playerName);
        } catch (e) {
          console.warn(e);
        }
      }

      // Launch the game
      joinGame(gameId, userId, playerName);

      $("#modal_background").hide();
    }
  });
}

/**
 * Join the game using the given player name.
 * @param playerName
 */
function joinGame(gameId, playerId, playerName) {
  // Create the web socket
  socket = io.connect("//" + document.domain + ":" + location.port);

  // Handle new turn
  socket.on("new_turn", handleNewTurn);

  // Handle leaderboard update
  socket.on("leaderboard_update", updateLeaderboard);

  // Join the default game
  socket.emit("join_game", gameId, playerId, playerName);

  // Handle end of turn
  socket.on("end_of_turn", handleEndOfTurn);

  // Handle player results
  socket.on("player_results", showPlayerResults);
}

/**
 * Update the leaderboard to show top ten players and user rank.
 * @param data
 */
function updateLeaderboard(data) {
  // Update player rank
  $("#user_rank_value").html(
    "(" + (data.player_rank + 1) + " / " + data.total_player + " players)"
  );

  // Update player global score
  $("#global_score_value").text(data.player_score);

  // Remove previous scores
  $(".score_row").remove();

  for (var i = 0; i < 10; i++) {
    if (data.player_rank == i) {
      $("#leaderboard table tr:last").after(
        '<tr class="score_row user_score"><td>' +
          (i + 1) +
          `</td><td>${data.player_name || username || ""} (You)</td><td>` +
          data.player_score +
          "</td></tr>"
      );
    } else if (data.top_ten[i]) {
      var row = $('<tr class="score_row">')
        .append($("<td>").text(i + 1))
        .append($("<td>").text(data.top_ten[i].player_name))
        .append($("<td>").text(data.top_ten[i].score));

      $("#leaderboard table tr:last").after(row);
    }
  }

  if (data.player_rank >= 10) {
    $("#leaderboard table tr:last").after(
      '<tr class="score_row user_score"><td>' +
        (data.player_rank + 1) +
        `</td><td>${data.player_name || username || ""} (You)</td><td>` +
        data.player_score +
        "</td></tr>"
    );
  }
}

/**
 * Start a new game turn.
 * Show the city to locate and listen for player answers.
 * @param data
 */
function handleNewTurn(data) {
  console.log("New turn", data);

  // Clear potential markers from previous turn
  markerGroup.clearLayers();

  // Update game rules to show the city to find
  $("#game_rules").html(
    'Locate <span class="city">' +
      data.current_turn.city +
      "</span> (" +
      data.current_turn.country +
      ")" +
      ` (${data.total_turns - data.remaining_turns + 1} / ${data.total_turns})`
  );

  // Show countdown timer
  progressBar.animate(1);

  // Enable answers for this turn
  map.on("click", answer);
  map.on("mousedown", answer);

  if (data.remaining_turns === 9) {
    hideLeaderboard();
  }
}

/**
 * End current turn.
 * Show best answer and correct answer for this turn.
 * @param data
 */
function handleEndOfTurn(data) {
  console.log("End of turn", data);
  // Reset zoom to default
  map.setZoom(2);

  // Disable answers listener
  map.off("click", answer);
  map.off("mousedown", answer);

  // Reset countdown timer
  progressBar.set(0);

  // Clear markers
  markerGroup.clearLayers();

  // Show best answer if there is one
  if (data.best_answer) {
    var bestMarker = createMarker(
      data.best_answer.lat,
      data.best_answer.lng,
      "marker-closest.svg"
    );
    bestMarker.bindPopup(
      `Closest answer: ${data.best_answer.player_name} (<b>` +
        round(data.best_answer.distance) +
        " km</b> away)"
    );
  }

  if (data.other_answers) {
    data.other_answers.forEach((answer) => {
      var bestMarker = createMarker(
        answer.lat,
        answer.lng,
        "marker-others.svg",
        [10, 10]
      );
      bestMarker.bindPopup(
        `${data.best_answer.player_name}: <b>` +
          round(data.best_answer.distance) +
          " km</b> away"
      );
    });
  }

  // Show correct answer
  var correctMarker = createMarker(
    data.correct_answer.lat,
    data.correct_answer.lng,
    "marker-correct.svg"
  );
  correctMarker.bindPopup(data.correct_answer.name);

  // Update game rules
  $("#game_rules").html(
    data.remaining_turns === 0
      ? "End of the round. Click to play again."
      : "Waiting for the next turn"
  );

  if (data.remaining_turns === 0) {
    showLeaderboard();
  }
}

/**
 * Show player results for the last turn.
 * @param data
 */
function showPlayerResults(data) {
  // Place a marker to identify user answer
  var userMarker = createMarker(data.lat, data.lng, "marker-yours.svg");

  // Show user score, ranking and distance
  var resultsText =
    '<div class="results"><b>' + round(data.distance) + " km</b> away: ";

  // Show user score
  if (data.score == 0) {
    resultsText += '<span class="score">Too far away!</span>';
  } else {
    resultsText +=
      '<span class="score">+<span id="score_value">0</span> points</span>';
  }

  resultsText +=
    "<br/>You are <b>#" +
    data.rank +
    "</b> out of <b>" +
    data.total +
    "</b> player(s) for this turn</div>";

  userMarker.bindPopup(resultsText).openPopup();

  if (data.score != 0) {
    // Animate player score
    animateValue("score_value", data.score);
  }
}

/**
 * Send user answer to the server.
 * @param e
 */
function answer(e) {
  // Clear previous markers if user is allowed to give multiple answers
  if (allowMultipleAnswer) {
    markerGroup.clearLayers();
  }
  // If user is not allowed to give multiple answer, turn off the answer listener
  else {
    map.off("click", answer);
  }

  // Mark the answer on the map
  createMarker(e.latlng.lat, e.latlng.lng, "marker-yours.svg");

  // Emit answer event
  socket.emit("answer", gameId, e.latlng.lat, e.latlng.lng);
}

/**
 * Create a marker on the leaflet map.
 * @param lat
 * @param lng
 * @param color
 * @returns {*}
 */
function createMarker(lat, lng, image, size = [38, 38]) {
  var icon = new L.Icon({
    iconUrl: cdnUrl + "/images/" + image,
    iconSize: size,
    iconAnchor: [19, 38],
    popupAnchor: [1, -34],
  });

  var marker = L.marker([lat, lng], { icon: icon }).addTo(map);

  markerGroup.addLayer(marker);

  return marker;
}

/**
 * Round a float value to 2 decimal
 * @param value
 * @returns {number}
 */
function round(value) {
  return Math.round(value * 100) / 100;
}

/**
 * Animate a value
 * @param elementID
 * @param newValue
 */
function animateValue(elementID, newValue) {
  var duration = 1000;
  // no timer shorter than 50ms (not really visible any way)
  var minTimer = 50;
  // calc step time to show all intermediate values
  var stepTime = Math.abs(Math.floor(duration / newValue));

  // never go below minTimer
  stepTime = Math.max(stepTime, minTimer);

  // get current time and calculate desired end time
  var startTime = new Date().getTime();
  var endTime = startTime + duration;
  var timer;

  function run() {
    var now = new Date().getTime();
    var remaining = Math.max((endTime - now) / duration, 0);
    var value = Math.round(newValue - remaining * newValue);
    $("#" + elementID).text(value);
    if (value == newValue) {
      clearInterval(timer);
    }
  }

  timer = setInterval(run, stepTime);
  run();
}

function createId(length) {
  // Alphanumeric characters
  const chars = "abcdefghijklmnopqrstuvwxyz";
  let id = "";
  for (let i = 0; i < length; i++) {
    id += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return id;
}

function getUsername() {
  const searchUN = new URLSearchParams(window.location.search).get("username");

  if (searchUN) {
    return searchUN;
  }
}

function getSetUserId() {
  let userId = new URLSearchParams(window.location.search).get(playerIdStorage);

  if (!userId) {
    if (typeof Storage !== "undefined") {
      if (localStorage.getItem(playerIdStorage)) {
        userId = localStorage.getItem(playerIdStorage);
      } else {
        userId = createId(20);
        localStorage.setItem(playerIdStorage, userId);
      }
    } else {
      userId = createId(20);
    }
  }
  return userId;
}
