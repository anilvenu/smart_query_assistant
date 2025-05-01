Study the project I have shared here. It is an LLM based smart query assistant that will take user query and find an appropriate verified query and apply changes to that to get answer to user question. 

[1] The YAML for verified queries need to be enhanced:
'questions' list instead of question singleton. 
There needs to be 'instructions' for tailoring the query. 
'verified_at' needs to be timestamp
I have added 'follow_up' which is a list of suggested follow up questions, basically linking to other verified queries on the YAML. You will need to help me make sure I have a healthy collection of follow ups and verified queries for the ones referenced.
I have updated the first verified query and will need your help with refining the rest and building a few more for the follow ups from the first one.

[3] This solution also needs to be enhanced. 
The verified queries and questions need to be stored in Postgres. 
Tables: 
verified_query - contains the verified queries from the YAML.
follow_up - vq_id and follow up vq id 
question - question and vq_id because there can be more than one question mapped to a vq. The question needs to include a vector embedding column for the question

There needs to be a script to create these tables on Postgres

There needs to be a verified_query.py that will have functions to 
data class for verified query (torch.vector will be the type for the vector)

get verified query using query id
get verified queries that uses vector search using question and returns up to n matching vqs
get_best_query that accepts question, then gets verified queries matched for the question and then selects the best among the results using LLM
get_query_recommendations that accepts a vq and context made up of user question and context and reference data and returns instructions for taloring the query to meet the user question
(you will see above that I have split the selection of best query and recommendation into different steps. tell me if this is a good idea)
get_follow_ups that will get the list of follow up verified query for the query id 

This is the enhanced overall flow.

1.Get Calendar Context (last month, this year)
2.Get User Context (resolve my team, my LOB, my region etc.) For the purpose of this project, you can create a user_profile.ini file and read this from there. 
3.Get Session Context (last query, summary of user intent during the session)
4.Clarification Agent (LLM reviews user question and contexts and determines if there is any clarification is needed and asks for the clarification)
5.Verified Query Search (after the optional clarification, the query is used to get the best query from vq using vector search and LLM based selection from the search results)
6.Query Recommendation Agent (gets recommendation for query modiification from LLM)
7.Query Adjustment Agent (LLM that performs modifications on query based on recommendation, and gives modified explanation for the query, based on original explanation and the old and new sql)
8.Query Review Agent (LLM reviews user question, vq and modified query and determines if the query looks okay, and makes correction recommendation if abslutely needed) - this goes back to 7 and back to review agent. after N=2 iterations, the reviewer passes to query execution (noting any residual concerns)
9.Query Execution Agent (executes the query on insurance_db)
10.Visualization Recommendation Agent (takes the user question, modified explanation, sample data and LLM recommends visualizations for the data)
11.Visualization Build Agent (coder LLM that will generate the visualization using plotly)
12.Conversation Planning Agent (gets the follow up vqs for the vq. for each follow up vq, create one question based on vq's questions that aligns with the current conversation)

Claude, I want you to first give me a plan to do these enhancements, because this is a major enhancement. Once we agree, you should generate yAML, code, sctand tests.