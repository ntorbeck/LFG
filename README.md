# LFG
Looking For Group is a web application designed to facilitate the creation of, and communication within, Dungeons and Dragons adventuring groups.  
#### LFG's major features include:
- An internal messaging system
- Campaign Browser
- Character and Campaign Management
- Campaign Creator
- Character Creator

#### Images:
Lfg logo, fail, and success pngs where designed by me.  
I used https://favicon.io/favicon-converter/ to create the favicon.ico.  
Table sorting arrows are from https://github.com/DataTables/DataTables/tree/master/media/images.

#### CSS:
I used https://bootswatch.com/darkly/ as a base and modified parts to suit my aesthetic.

#### Starting Pages:
1. login.html
    - Modified from CS50 Finance project.
    - Shows lfg_logo.png, acts as homepage until user logs in.
2. register.html
    - From CS50 Finance, allows user to create an account.

#### Internal Messaging:
The internal messaging system works like a simplier version of email.  
Messages are only removed from the database if both the sender and receiver have decided to delete the message.  
- If only one user has deleted the message, the message is hidden from the user that deleted it.

After logging in, the homepage is set to the user's inbox.  
There is a mini navbar that allows you navigate between your inbox, sent messages, and the message composition page.
3. inbox.html
   - Shows a searchable, paginated table by using datatables.
   - Clicking on a table row allows you to view that message.
   - Read and unread messages show visual difference.
   - You can mark multiple messages as read or unread, and delete multiple messages at once using checkboxes.
4. sent.html
   - Shows a searchable, paginated table.
   - Clicking on a table row allows you to view that message.
   - You can delete multiple messages at once using checkboxes.
5. compose.html
   - Shows a form that allows you to send an up to 5000 character message to a single user at a time.
   - Clicking send inserts your message into the messages table...
     - Only if the "To" field contains a valid username and you have provided a subject and message.
6. message.html
   - Shows sender and receiver username, subject, and message.
   - Clicking delete button will remove the message from your inbox/sent messages.
   - Shows reply button only if you are the receiver of the message.
     - Clicking reply opens compose.html with sender's username and original subject filled in.

#### Campaign Browser:
The campaign browser shows you all campaigns the you are capable of joining.  
Hidden from view are any campaigns you have created or already joined, and any campaigns that have reached their maximum player limit.

7. browse.html
   - Shows a searchable, paginated table.
   - Clicking on a table row allows you to view that campaign's page.

#### Character and Campaign Management:
Each user can have up to 10 characters and 10 campaigns created at one time.  
You have the ability to edit these assets after creation and delete any assets you no longer need.  
By deleting assets you can free up slots for creating new ones.

8. camp.html
   - Shows you all the information for a campaign, including a table showing any characters that have already joined.
   - This table is searchable and paginated.
   - Clicking on a character takes you to the character's page, showing more information about it.
   - Clicking the Dungeon Master's username opens compose.html with that username filled in.
     - If you are the DM, the username is replaced with "You" and is not clickable.
   - Clicking join takes you to join.html, here you can select one of your characters to join the campaign.
     - You will only see the characters that have not already joined a campaign.
     - After joining, the join button is replaced with a leave button.
     - Clicking leave removes your character from the campaign, meaning its campaign id is reset to null.
   - If you are the DM, you will see an edit and delete button, instead of a join/leave button.
     - Clicking delete will remove your campaign from the database and all joined character's will have their campaign id reset to null.
     - Clicking edit will open camp_edit.html.
9. camp_edit.html
   - Shows a form that allows you to edit your campaign.
   - Clicking update will resubmit your campaign to the database, making any changes.
   - Clicking cancel will return you to camp.html without touching the database.
10. char.html
    - Shows you most of the information for a character.
      - Character backstories can only be viewed by the character's Player(owner) or their Dungeon Master.
    - Clicking the Player's username opens compose.html with that username filled in.
      - If you are the Player, the username is replaced with "You" and is not clickable.
    - If you are the character's DM, you will see a remove button.
      - Clicking remove will remove the character from your campaign, resetting its campaign id to null.
    - If you are the Player, you will see an edit and delete button.
      - Clicking delete will remove your character from the database and from any campaign they have joined.
      - Clicking edit will open char_edit.html.
11. char_edit.html
    - Shows a form that allows you to edit your character and add additional information that is not included on the creation form.
    - Clicking update will resubmit your caharacter to the database, making any changes.
    - Clicking cancel will return you to char.html without touching the database.

#### Campaign Creator:
12. camp_gen.html
    - Modified from CS50 Survey project, uses SQLite for the database instead of CSV.
    - Shows a simple form asking for information about your campaign.
    - By creating a campaign, you are set as its Dungeon Master, giving you special privileges.
      - As dm you can see the backstories of any characters that join your campaign(if one is provided).
      - You can remove any characters from your campaign by visiting their character page.
    - Clicking submit inserts your campaign into the campaigns table(if you have provided all required information).
    - After submission you are redirected to campaigns.html.
13. campaigns.html
     - Shows a table containing all the campaigns you have created or joined with one of your characters.
     - This table is searchable and paginated.
     - Clicking on a row will take you to that campaign's page.

#### Character Creator:
14. char_gen.html
    - Modified from CS50 Survey project, uses SQLite for the database.
    - Shows a form that allows you to quickly create a character.
      - It currently only supports 5th edition characters.
    - Clicking submit inserts your character into the characters table(if you have provided all required information).
    - After submission you are redirected to characters.html.
15. characters.html
    - Shows a table containing all your characters.
    - This table is searchable and paginated.
    - Clicking on a row will take you to that character's page.

#### Additional Pages:
16. error.html
    - Modified from CS50 Survey project.
    - Shows error code, a bulleted list of errors, and lfg_fail.png.
17. layout.html
    - Modified from CS50 Finance project.
    - Contains main navbar, shows differently based on log in status.
    - Contains "get flashed messages".
      - Shows a red alert flanked by lfg_fail.png for error messages.
      - Shows a green alert flanked by lfg_success.png for success messages.

#### helpers.py:
1. datetime_convert  
   - Converts date timestamps to a more readable format.
2. login_required  
   - From CS50 Finance project.
   - Makes sure user is logged in to access most pages/features.  
3. time_convert  
   - Converts time to 12 hour format with AM/PM.
