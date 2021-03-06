#imports 

#Pandas dataframes
import pandas as pd

#Regular Expressions
import re

# Sqlite - simple database
import sqlite3

# For fetching/reading remote data
import urllib
import urllib.request
from urllib.request import urlopen

#for processing html
#pip3 install lxml
from lxml import etree
from bs4 import BeautifulSoup

#for visualizations
import matplotlib.pyplot as plt
import numpy as np
import math

"""Read in the Data 
 - using pandas read_html()
"""

df = pd.read_html('https://questionnaire-148920.appspot.com/swe/data.html')[0]
df.head()

"""Clean the Data
 - Remove $ and ,'s from Salary
 - Seperate first and last name
 - Drop uneccesary columns
"""

def clean_salary(x):
  y = re.sub("[^\d]", "", str(x))
  if (y.isnumeric()):
    return float(y)
  else:
    return None
    

#use apply to call the function over each element, returning a new Series
df['Salary'] = df['Salary'].apply(clean_salary)

#split first and last name 
df[['Lastname', 'Firstname']] = df['Player'].str.split(', ', expand=True)

#drop Year & Level 
df = df.drop(columns=['Year', 'Level', 'Player'])

df.head()

"""Determine Qualifying Offer
 - Find the top 125 salaries 
 - Calculate their average
"""

#find highest 125 salaries
#used as resource: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.nlargest.html
top_salaries = df['Salary'].nlargest(n=125).to_frame()

#calculate mean of those salaries
qual_offer = top_salaries.mean()[0]

print("Qualifying offer: " + "${:,.2f}".format(qual_offer))

"""Determine Qualifying Offer using SQL
 - using sqlite3
 - determine top 125 salaries
 - calculate average
"""

#connect and convert from pandas dataframe to SQL database
conn = sqlite3.connect('local.db')
df.to_sql('salary_guide', con=conn, if_exists="replace")

query = '''SELECT AVG(Salary) as Qualifying_Offer
           FROM (SELECT Firstname, Lastname, Salary 
                FROM salary_guide 
                ORDER BY Salary DESC LIMIT 125 )'''
avg_df = pd.read_sql_query(query, conn)

qual_offer_sql = avg_df['Qualifying_Offer'][0]
print("Qualifying offer: " + "${:,.2f}".format(qual_offer_sql))

"""Create visualizations to help determine if we should present our departing free agent with this qualifying offer by comparing their statisics to those of players with the top 125 salaries. 
 - scrape wikipedia for statistics using player's name
 - create dataframe with relevent statistics 
 - calculate averages based on player's position
 - create visualizations to help analyze this data
"""

#create table with top 125 salaries and players
df.to_sql('salary_guide', con=conn, if_exists="replace")

query = '''SELECT Firstname, Lastname, Salary 
            FROM salary_guide 
            ORDER BY Salary DESC LIMIT 125'''
top_125_df = pd.read_sql_query(query, conn)

top_125_df.head()

#used lelctures from UPenn's MCIT Course "545: Big Data Analytics" Modules 1 & 2 as resources for this section
#used as reference = https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.iterrows.html
crawl_list = []
pages = []
wiki_df = pd.DataFrame(columns = ['Firstname', 'Lastname', 'Wiki Page'])

#loop through top 125 players and create their wikipedia pages
for i, series in top_125_df.iterrows():
  url = 'https://en.wikipedia.org/wiki/' + top_125_df['Firstname'][i].replace(' ', '_') +  '_' + top_125_df['Lastname'][i].replace(' ', '_')
  crawl_list.append(url)
  # Some of the accent characters won't work, need to convert them into an HTML URL
  #split the URL, then use "parse.quote" to change the structure, then re-form the URL
  url_list = list(urllib.parse.urlsplit(url))
  url_list[2] = urllib.parse.quote(url_list[2])
  url_ascii = urllib.parse.urlunsplit(url_list)
  try:
    response = urllib.request.urlopen(url_ascii)
    #Save page and url for later use.
    pages.append(response)
  except urllib.error.URLError as e:
    #if unable to open the page, just add None 
    pages.append(None)
    #print(e.reason)
  
top_125_df['Wiki Page'] = crawl_list
top_125_df['url_response'] = pages
top_125_df.head()

#create column headers for possible statistics 
top_125_df = pd.concat([top_125_df,pd.DataFrame(columns=['Position', 'Age', 'Earned run average', 'Strikeouts', 'Batting average', 'Home runs', 'Runs batted in'])])

#to avoid warning given
#https://stackoverflow.com/questions/20625582/how-to-deal-with-settingwithcopywarning-in-pandas
pd.options.mode.chained_assignment = None

#loop through each player, scrape wikipedia page for relevant statistics 

for i, series in top_125_df.iterrows():  
    #make sure only reading pages that worked previously
    if (top_125_df['url_response'][i] != None):
      source = urlopen(top_125_df['Wiki Page'][i]).read()
      
      #create a DOM tree of the page
      tree = etree.HTML(source.decode("utf-8"))  

      #get player age
      age = tree.xpath('//table[contains(@class,"vcard")]//span[@class="noprint ForceAgeToShow"]/text()')
      if len(age) > 0:
        top_125_df['Age'][i] = int((age[0])[-3:-1])
  
      #get player position
      position = tree.xpath('//table[contains(@class,"vcard")]//td[@class="infobox-full-data"]//a/text()')      
      if len(position) > 1:
        if "pitcher" in str(position[0]).lower():
          top_125_df['Position'][i] = "Pitcher"
        else:
          top_125_df['Position'][i] = str(position[0])
      
      #get additional statistics ('Strikeouts', 'Home runs', 'Runs batted in', 'Earned run average', 'Batting average')
      stat_labels = tree.xpath('//table[contains(@class,"vcard")]//tr//th/a/text()')
      stat_data = tree.xpath('//table[contains(@class,"vcard")]//tr//td[contains(@class, "infobox-data")]/text()')

      row_headers_int = ['Strikeouts', 'Home runs', 'Runs batted in']
      row_headers_float = ['Earned run average', 'Batting average']

      #loop through labels found and if they are in the list above, add that data to the table
      for j in range(len(stat_labels)):
        if stat_labels[j] in row_headers_int:
          top_125_df[stat_labels[j]][i] = int(stat_data[j].replace(",",""))
        elif stat_labels[j] in row_headers_float:
          top_125_df[stat_labels[j]][i] = float(stat_data[j])

top_125_df.head()

#general cleaning 

#drop wikipedia site - no longer needed
top_125_df = top_125_df.drop(columns = ['Wiki Page', 'url_response'])

#rename column headers - replace spaces with underscores
top_125_df.columns = top_125_df.columns.str.replace(' ','_')

#Use sqlite for table - will use for future queries
top_125_df.to_sql('top_125_stats', con=conn, if_exists="replace")
top_125_stats_sql = pd.read_sql_query('SELECT * FROM top_125_stats', conn)
top_125_stats_sql.head()

#serperate pitcher stats from other players
query = '''SELECT Firstname, Lastname, Position, Salary, Age, Earned_run_average, Strikeouts 
          FROM top_125_stats 
          WHERE Position = "Pitcher"'''
pitcher_stats = pd.read_sql_query(query, conn)
pitcher_stats.head()

#serperate pitcher stats from other players
query = '''SELECT Firstname, Lastname, Position, Salary, Age, Batting_average,	Home_runs,	Runs_batted_in
          FROM top_125_stats 
          WHERE Position != "Pitcher"'''
player_stats = pd.read_sql_query(query, conn)
player_stats

#calculate averages stats for pitchers

query = '''SELECT Position, AVG(Salary) as Avg_Salary, AVG(Age) AS Avg_Age, AVG(Earned_run_average) as Avg_ERA, AVG(Strikeouts) AS Avg_Strikeouts
          FROM top_125_stats
          WHERE Position = "Pitcher"
          GROUP BY Position'''
avg_pitcher_stats = pd.read_sql_query(query, conn)
avg_pitcher_stats.head()

#calculate average stats remaining positions
query = '''SELECT Position, AVG(Salary) as Avg_Salary, AVG(Age) AS Avg_Age, AVG(Batting_average) as Avg_Batting_average, AVG(Home_runs) AS Avg_Home_runs, AVG(Runs_batted_in) as Avg_Runs_batted_in
          FROM top_125_stats
          WHERE Position != "None" and Position != "Pitcher"
          GROUP BY Position'''
avg_player_stats = pd.read_sql_query(query, conn)
avg_player_stats

"""###**Time to see the graphs!**

For each of the graphs below:
 - a **purple** line represents the qualifying offer
 - a **red** line represents the average for the statistic for that position
 - a **blue** line represents the line of best fit for the given scatter plot



"""

def create_scatterplot(x, y, x_label, y_label, position, avg_x, avg_y):
  #create scatter plot with x & y data
  plt.scatter(x, y)
  
  #set titles/labels
  title = position + " " + x_label + " vs " + y_label
  plt.title(title)
  plt.xlabel(x_label)
  plt.ylabel(y_label)

  #create line of best fit
  m, b = np.polyfit(x, y, 1)
  plt.plot(x, m*x+b)

  #plot average point & lines for given position/stat
  plt.plot(avg_x,avg_y,'ro') 
  plt.axvline(x = avg_x, color = 'r')
  plt.axhline(y = avg_y, color = 'r')

  #plot qualifying offer
  plt.axhline(y = qual_offer/1000000, color = 'purple')

  #show the final graph
  plt.show()

"""First, the Pitchers: """

#ERA
create_scatterplot(pitcher_stats['Earned_run_average'], pitcher_stats['Salary']/1000000, "Earned Run Average", "Salary", "Pitcher", avg_pitcher_stats['Avg_ERA'][0], avg_pitcher_stats['Avg_Salary'][0]/1000000)
#Strikeouts
create_scatterplot(pitcher_stats['Strikeouts'], pitcher_stats['Salary']/1000000, "Strikeouts", "Salary", "Pitcher", avg_pitcher_stats['Avg_Strikeouts'][0], avg_pitcher_stats['Avg_Salary'][0]/1000000)
#Age
create_scatterplot(pitcher_stats['Age'], pitcher_stats['Salary']/1000000, "Age", "Salary", "Pitcher", avg_pitcher_stats['Avg_Age'][0], avg_pitcher_stats['Avg_Salary'][0]/1000000)

"""Then, the remaining positions:"""

#loop through all of the stats for each of the positions to display their graphs 
stat_list = ['Age', 'Batting_average',	'Home_runs', 'Runs_batted_in']
for i in range(len(avg_player_stats['Position'])):
  position = avg_player_stats['Position'][i]
  print(position)
  for stat in stat_list:
    x = player_stats[stat]
    y = player_stats['Salary']/1000000
    x_label = stat
    y_label = 'Salary (in millions)'
    position = position
    avg_x = avg_player_stats['Avg_' + stat][i]
    avg_y = avg_player_stats['Avg_Salary'][i]/1000000
    #ensure stat exists before plotting
    if(not math.isnan(player_stats[stat][i])):
      create_scatterplot(x, y, x_label, y_label, position, avg_x, avg_y)
  print("\n")
