import discord
import discord.ui
from discord import app_commands
from discord.ui import Select, View
import requests
import json
import asyncio
import config
import ratemyprofessor as rmp

def run_discord_bot():
    TOKEN = config.TOKEN

    session = '2022W' #to get first section in this session
    school_name = "University of British Columbia"
    school = rmp.get_school_by_name(school_name)

    intents = discord.Intents.default()  
    intents.message_content = True
    client = discord.Client(intents=intents)

    tree = app_commands.CommandTree(client)

    @tree.command(name = "course", description = "Get Info on a UBC Course")
    async def first_command(interaction: discord.Interaction, course_code: str, course_number: str):
        code = course_code.upper()

        grade_api = f'https://ubcgrades.com/api/v3/course-statistics/UBCV/{code}/{course_number}'
        sections_api = f'https://ubcgrades.com/api/v3/sections/UBCV/{session}/{code}/{course_number}'
        
        grade_request = requests.get(grade_api)
        sections_request = requests.get(sections_api)

        if (grade_request.status_code == 200):
            api_json = json.loads(grade_request.content)
            first_section = str(json.loads(sections_request.content)[0])

            average = round(float(api_json['average_past_5_yrs']), 2)
            title = api_json['course_title']
            ssc = f'https://courses.students.ubc.ca/cs/courseschedule?pname=subjarea&tname=subj-course&dept={code}&course={course_number}'
            
            #ubcgrades no longer has the overall section so it puts you on the first available section
            ubc_grades = f'https://ubcgrades.com/#UBCV-{session}-{code}-{course_number}-{first_section}' 

            await interaction.response.send_message(
                embed=discord.Embed(
                    title=f'{code} {course_number}: {title}',
                    description=f'5 Year Rolling Average: {average}% \n[SSC Link]({ssc}) \n[UBCGrades Link]({ubc_grades})',
                )
            )
        else:
            await interaction.response.send_message(f"{code} {course_number} doesn't seem to exist!")
    
    @tree.command(name = "prof", description = "Get RateMyProfessors Info on a UBC Professor")
    async def second_command(interaction: discord.Interaction, name: str):
        
        async def send_prof(interaction, professor, from_list=False):
            rating = "{:.1f}".format(professor.rating)
            difficulty = "{:.1f}".format(professor.difficulty)
            rmp_link = f'https://www.ratemyprofessors.com/professor/{professor.id}'
            
            embed = discord.Embed(
                        title=f'{professor.name}',
                        description=f"""
                        *{professor.department}*\n
                        Rating: {rating}
                        Difficulty: {difficulty}
                        Total Ratings: {professor.num_ratings}
                        [See more on RateMyProfessors]({rmp_link})
                        """
                    )

            await asyncio.sleep(1)

            if (not from_list):
                await interaction.followup.send(embed=embed, ephemeral=False)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=False)

        await interaction.response.defer(ephemeral=True) #have to defer the response otherwise will timeout due to slow API call
        
        try:
            professors = rmp.get_professors_by_school_and_name(school, name) #this is a very slow API call
            professors = list(filter(lambda x: x.school.name == school_name, professors)) #filter out any profs that don't go to the proper school
            
            if (len(professors) == 0):
                await interaction.followup.send(
                    embed=discord.Embed
                    (
                        title="No professor with that name found!",
                        description="Please try again."
                    ))
            #TODO, figure out how to make this send_prof call non ephemeral
            elif len(professors) == 1:
                await send_prof(interaction, professors[0])
            else:
                professors.sort(key=lambda x: x.num_ratings, reverse=True) #sort in descending order of num_ratings
                options = []
                i = 0
                for professor in professors:
                     options.append(discord.SelectOption(
                          label=f"{professor.name}: {professor.num_ratings} ratings",
                          value=i,
                          description=f"{professor.department}"))
                     i+=1
                     
                select = Select(options=options)

                async def callback(interaction):
                     await send_prof(interaction, professors[int(select.values[0])], True)
                     await message.delete()
                
                select.callback = callback

                view = View()
                view.add_item(select)

                message = await interaction.followup.send(
                    embed=discord.Embed(
                        title="Multiple Professors Found!",
                        description="Please select one of the following professors:"
                    ), 
                    view=view, ephemeral=True
                )
                
        except Exception as e:
            print(e)
            print(f'Error looking up {name}')
            await interaction.followup.send(f'There was an internal error! Please try again!')
    
    @tree.command(name = "building", description = "Get Information on a UBC Building")
    async def third_command(interaction: discord.Interaction, code: str):
        building_code = code.upper()
        building_api = f'https://mg3xyuefal.execute-api.us-east-2.amazonaws.com/ubcbuildings/building?code={building_code}'
        request = requests.get(building_api)
        print(request.status_code)
        if request.status_code == 200:
            building_json = json.loads(request.content)
            name = building_json['name']
            address = building_json['address']
            #use this link for directions between buildings, for next command
            #maps_link = f'https://www.google.com/maps/dir/?api=1&origin={address.replace(" ", "+")}+Vancouver,+BC&destination=UBC+Fountain&travelmode=walking'
            maps_link=f'[{address}](https://www.google.com/maps?q={address.replace(" ", "+")}+Vancouver,+BC)'
            await interaction.response.send_message(
                embed=discord.Embed(
                    title=f'{building_code}',
                    description=f'''
                    *{name}*\n
                    {maps_link}''',
                )
            )
        else:
            await interaction.response.send_message(
                embed=discord.Embed
                (
                    title="No building with that code found!",
                    description="Please try again."
                ))


    @client.event
    async def on_ready():
        await tree.sync()
        print(f'{client.user} is now running!')
    
    client.run(TOKEN)