/**
 * Spotify Listener Research Survey — auto-builder for Google Forms
 * ---------------------------------------------------------------------------
 * HOW TO USE
 *   1. Go to https://script.google.com  →  New project
 *   2. Delete the default code, paste this whole file
 *   3. Click  Run  (▶)  on  buildSpotifySurvey
 *   4. Approve the one-time permission prompt
 *   5. The execution log prints the live edit + share URLs of the new Form
 *
 * The survey segments every respondent into one of the six audience types
 * surfaced by the review analysis (Free Tier, Super, Moderate, Light,
 * Previously Active, Programmed) and validates the six research questions:
 * discovery, repeat listening, recommendations, segment pain, listening
 * behaviours, and unmet needs.
 */

function buildSpotifySurvey() {
  var form = FormApp.create('Spotify Listening Experience — Research Survey');

  form.setDescription(
    'Help us understand how people really use Spotify. This takes about 5–7 minutes. ' +
    'There are no right answers — we want your honest experience with discovery, ' +
    'recommendations, repetition, ads, and the features you wish existed. ' +
    'Responses are anonymous and used only for product research.'
  );
  form.setProgressBar(true);
  form.setCollectEmail(false);

  // ─────────────────────────────────────────────────────────────────────
  // SECTION A — About you & how you listen  (drives segmentation)
  // ─────────────────────────────────────────────────────────────────────
  form.addSectionHeaderItem()
    .setTitle('Section 1 — About You')
    .setHelpText('A few quick questions so we can understand what kind of listener you are.');

  form.addMultipleChoiceItem()
    .setTitle('How long have you used Spotify?')
    .setChoiceValues([
      'Less than 1 month',
      '1–6 months',
      '6 months – 1 year',
      '1–3 years',
      'More than 3 years',
      'I no longer use it'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('What plan are you currently on?')
    .setChoiceValues([
      'Free (with ads)',
      'Premium Individual',
      'Premium Duo or Family',
      'Premium Student',
      'I cancelled / no longer subscribe'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('How often do you listen to Spotify?')
    .setChoiceValues([
      'Multiple times a day',
      'About once a day',
      'A few times a week',
      'Rarely / occasionally'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Which best describes how you usually start listening?')
    .setChoiceValues([
      'I search for and pick specific songs, artists, or playlists',
      'I let autoplay, radio, or shuffle decide for me',
      'A roughly even mix of both'
    ])
    .setHelpText('This helps us tell active choosers from passive / programmed listeners.')
    .setRequired(true);

  form.addCheckboxItem()
    .setTitle('Which Spotify features do you regularly use?')
    .setChoiceValues([
      'Discover Weekly',
      'Release Radar',
      'Daily Mix',
      'Wrapped',
      'Blend',
      'Liked Songs / your own library',
      'Playlists you created',
      'Autoplay / Radio',
      'None of these'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Have you ever cancelled Premium or seriously considered leaving Spotify?')
    .setChoiceValues([
      'Yes — I cancelled / stopped using it',
      'Yes — I seriously considered it',
      'No'
    ])
    .setRequired(true);

  form.addCheckboxItem()
    .setTitle('If you left or considered leaving, where did you go (or consider going)?')
    .setChoiceValues([
      'Apple Music',
      'YouTube Music',
      'Tidal',
      'Amazon Music',
      'Stopped paid streaming altogether',
      'Not applicable'
    ])
    .setRequired(false);

  // ─────────────────────────────────────────────────────────────────────
  // SECTION B — Discovering new music  (Research Q1)
  // ─────────────────────────────────────────────────────────────────────
  form.addPageBreakItem()
    .setTitle('Section 2 — Discovering New Music')
    .setHelpText('How well Spotify helps you find music you have not heard before.');

  form.addScaleItem()
    .setTitle('How satisfied are you with how Spotify helps you discover new music?')
    .setBounds(1, 5)
    .setLabels('Very dissatisfied', 'Very satisfied')
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('How often do you find genuinely new artists or songs you love through Spotify?')
    .setChoiceValues(['Often', 'Sometimes', 'Rarely', 'Never'])
    .setRequired(true);

  form.addCheckboxItem()
    .setTitle('What gets in the way of discovering new music? (select all that apply)')
    .setChoiceValues([
      'Recommendations feel repetitive',
      'Suggestions don\'t match my taste',
      'Too much focus on what I already listen to',
      'Discovery features are hard to find or navigate',
      'App bugs or performance issues',
      'I don\'t have trouble discovering music'
    ])
    .showOtherOption(true)
    .setRequired(false);

  form.addParagraphTextItem()
    .setTitle('Describe a time Spotify recommended something that worked really well — or really didn\'t.')
    .setRequired(false);

  // ─────────────────────────────────────────────────────────────────────
  // SECTION C — Repetition & control  (Research Q2)
  // ─────────────────────────────────────────────────────────────────────
  form.addPageBreakItem()
    .setTitle('Section 3 — Repetition & Control')
    .setHelpText('How often you hear the same things, and how in-control you feel.');

  form.addScaleItem()
    .setTitle('How often does it feel like Spotify plays the same songs over and over?')
    .setBounds(1, 5)
    .setLabels('Never', 'Constantly')
    .setRequired(true);

  form.addCheckboxItem()
    .setTitle('When does repetition bother you most? (select all that apply)')
    .setChoiceValues([
      'On shuffle',
      'In autoplay / radio',
      'In algorithmic playlists (e.g. Daily Mix)',
      'Even in my own playlists',
      'Repetition doesn\'t bother me'
    ])
    .setRequired(false);

  form.addScaleItem()
    .setTitle('I feel in control of what plays next.')
    .setBounds(1, 5)
    .setLabels('Strongly disagree', 'Strongly agree')
    .setRequired(true);

  // ─────────────────────────────────────────────────────────────────────
  // SECTION D — Recommendations & personalization  (Research Q3)
  // ─────────────────────────────────────────────────────────────────────
  form.addPageBreakItem()
    .setTitle('Section 4 — Recommendations')
    .setHelpText('How well the algorithm understands your taste.');

  form.addScaleItem()
    .setTitle('Spotify\'s recommendations match my taste.')
    .setBounds(1, 5)
    .setLabels('Strongly disagree', 'Strongly agree')
    .setRequired(true);

  form.addScaleItem()
    .setTitle('I feel Spotify keeps me in a "bubble" of very similar music.')
    .setBounds(1, 5)
    .setLabels('Strongly disagree', 'Strongly agree')
    .setRequired(true);

  form.addCheckboxItem()
    .setTitle('What frustrates you most about recommendations? (select all that apply)')
    .setChoiceValues([
      'Too repetitive',
      'Too random / off-base',
      'Ignores my mood or context',
      'Pushes podcasts / audiobooks I don\'t want',
      'I can\'t influence or reset them',
      'Nothing — they work well for me'
    ])
    .showOtherOption(true)
    .setRequired(false);

  // ─────────────────────────────────────────────────────────────────────
  // SECTION E — How & why you listen  (Research Q5)
  // ─────────────────────────────────────────────────────────────────────
  form.addPageBreakItem()
    .setTitle('Section 5 — How & Why You Listen')
    .setHelpText('The situations music plays a role in for you.');

  form.addCheckboxItem()
    .setTitle('In which situations do you mainly listen? (select all that apply)')
    .setChoiceValues([
      'Focus / work / study',
      'Workout / exercise',
      'Commute / driving',
      'Relaxing / sleep / background',
      'Mood or emotional listening',
      'Social settings / parties'
    ])
    .showOtherOption(true)
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('In those moments, what are you mainly trying to get from Spotify?')
    .setHelpText('e.g. "music that keeps me focused without distracting me", "energy for the gym".')
    .setRequired(false);

  form.addScaleItem()
    .setTitle('How well does Spotify serve your main listening situation?')
    .setBounds(1, 5)
    .setLabels('Very poorly', 'Very well')
    .setRequired(true);

  // ─────────────────────────────────────────────────────────────────────
  // SECTION F — Ads, frustrations & unmet needs  (Research Q6 + key themes)
  // ─────────────────────────────────────────────────────────────────────
  form.addPageBreakItem()
    .setTitle('Section 6 — Frustrations & Wishes')
    .setHelpText('The things that bug you and the things you wish existed.');

  form.addMultipleChoiceItem()
    .setTitle('How disruptive are ads to your listening?')
    .setChoiceValues([
      'I\'m on Premium — no ads',
      'Not disruptive',
      'Somewhat disruptive',
      'Very disruptive',
      'So disruptive it makes me consider leaving'
    ])
    .setHelpText('Ads are the top pain point for free-tier listeners — your input matters here.')
    .setRequired(true);

  form.addCheckboxItem()
    .setTitle('Which features do you most wish Spotify had — or brought back? (select all that apply)')
    .setChoiceValues([
      'Better queue control',
      'Truly random ("real") shuffle',
      'Better search and filtering',
      'More control over recommendations',
      'Lyrics improvements',
      'Cheaper or more flexible plans',
      'Higher-quality / hi-fi audio',
      'Fewer / shorter ads on free tier'
    ])
    .showOtherOption(true)
    .setRequired(false);

  form.addParagraphTextItem()
    .setTitle('What is the single biggest thing Spotify could fix or add for you?')
    .setRequired(true);

  form.addScaleItem()
    .setTitle('How likely are you to recommend Spotify to a friend?')
    .setBounds(0, 10)
    .setLabels('Not at all likely', 'Extremely likely')
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('Anything else you\'d like to tell us about your Spotify experience?')
    .setRequired(false);

  // ─────────────────────────────────────────────────────────────────────
  Logger.log('✅ Form created.');
  Logger.log('Edit it here:   ' + form.getEditUrl());
  Logger.log('Share this URL: ' + form.getPublishedUrl());
}
