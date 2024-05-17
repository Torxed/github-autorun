import enum
import pydantic
import fastapi
import typing
import datetime
# from fastapi import Request, Response, HTTPException, status

app = fastapi.FastAPI()

class Types(enum.Enum):
	Repository :"Repository"

class ContentTypes(enum.Enum):
	json :"json"

class Visibility(enum.Enum):
	public :"public"
	private :"private"

class WebhookConfig(pydantic.BaseModel):
	content_type :str # ContentTypes
	insecure_ssl :int
	url :str

class LastResponse(pydantic.BaseModel):
	status :str
	code :int|None = None
	message :str|None = None

class Hook(pydantic.BaseModel):
	type :str #Types
	id :int
	name :str
	events :typing.List[str]
	config :WebhookConfig
	updated_at :datetime.datetime
	created_at :datetime.datetime
	url :str
	test_url :str
	ping_url :str
	deliveries_url :str
	last_response :LastResponse

class UserInfo(pydantic.BaseModel):
	login :str
	id :int
	node_id :str
	avatar_url :str
	gravatar_id :str
	url :str
	html_url :str
	followers_url :str
	following_url :str
	gists_url :str
	starred_url :str
	subscriptions_url :str
	organizations_url :str
	repos_url :str
	events_url :str
	received_events_url :str
	type :str
	site_admin :bool

class Repository(pydantic.BaseModel):
	id :int
	node_id :str
	name :str
	full_name :str
	private :bool
	owner :UserInfo
	html_url :str
	description :str
	fork :bool
	url :str
	forks_url :str
	keys_url :str
	collaborators_url :str
	teams_url :str
	hooks_url :str
	issue_events_url :str
	events_url :str
	assignees_url :str
	branches_url :str
	tags_url :str
	blobs_url :str
	git_tags_url :str
	git_refs_url :str
	trees_url :str
	statuses_url :str
	languages_url :str
	stargazers_url :str
	contributors_url :str
	subscribers_url :str
	subscription_url :str
	commits_url :str
	git_commits_url :str
	comments_url :str
	issue_comment_url :str
	contents_url :str
	compare_url :str
	merges_url :str
	archive_url :str
	downloads_url :str
	issues_url :str
	pulls_url :str
	milestones_url :str
	notifications_url :str
	labels_url :str
	releases_url :str
	deployments_url :str
	created_at :str
	updated_at :str
	pushed_at :str
	git_url :str
	ssh_url :str
	clone_url :str
	svn_url :str
	homepage :str
	size :int
	stargazers_count :int
	watchers_count :int
	language :str
	has_issues :bool
	has_projects :bool
	has_downloads :bool
	has_wiki :bool
	has_pages :bool
	has_discussions :bool
	forks_count :int
	archived :bool
	disabled :bool
	open_issues_count :int
	license :dict # .. todo:: make a useful struct
	# "license": {
	# 	"key": "gpl-3.0",
	# 	"name": "GNU General Public License v3.0",
	# 	"spdx_id": "GPL-3.0",
	# 	"url": "https://api.github.com/licenses/gpl-3.0",
	# 	"node_id": "MDc6TGljZW5zZTk="
	# },
	allow_forking :bool
	is_template :bool
	web_commit_signoff_required :bool
	topics :list # No idea what's in here
	visibility :str
	forks :int
	open_issues :int
	watchers :int
	default_branch :str
	


	mirror_url :str|None = None

class Greeting(pydantic.BaseModel):
	hook_id :int
	hook :Hook
	zen :str|None = None
	repository :Repository
	sender :UserInfo

@app.post('/github/')
async def webhook_landing(payload :Greeting, request :fastapi.Request, response :fastapi.Response):
	return fastapi.Response(
		status_code=202
	)
