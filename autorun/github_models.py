import enum
import pydantic
import typing
import datetime

"""
The three main models:
 * Ping
 * PullRequest
 * WorkflowJob

Those are the entry points used by FastAPI.
The rest are just fillers to accomodate the data sent by:
 * https://github.com/<owner>/<repo>/settings/hooks/
"""

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

class RepoInfo(pydantic.BaseModel):
	id :int
	node_id :str
	name :str
	full_name :str
	private :bool
	owner :UserInfo
	fork :bool
	html_url :str
	description :str
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

class Head(pydantic.BaseModel):
	label :str
	ref :str
	sha :str
	user :UserInfo
	repo :Repository


class PullRequestInfo(pydantic.BaseModel):
	url :str
	id :int
	node_id :str
	html_url :str
	diff_url :str
	patch_url :str
	issue_url :str
	number :int
	state :str
	locked :bool
	title :str
	user :UserInfo
	body :str
	created_at :datetime.datetime
	updated_at :datetime.datetime
	assignees :list
	requested_reviewers :list
	requested_teams :list
	labels :list
	draft :bool
	commits_url :str
	review_comments_url :str
	review_comment_url :str
	comments_url :str
	statuses_url :str
	head :Head
	base :Head
	_links :dict
	author_association :str
	mergeable_state :str
	merged :bool
	comments :int
	review_comments :int
	commits :int
	additions :int
	deletions :int
	changed_files :int
	maintainer_can_modify :bool
	merge_commit_sha :str|None = None
	auto_merge :bool|None = None
	active_lock_reason :bool|None = None
	mergeable :bool|None = None
	rebaseable :bool|None = None
	merged_by :str|None = None
	closed_at :datetime.datetime|None = None
	merged_at :datetime.datetime|None = None
	assignee :str|None = None
	milestone :str|None = None 

class Ping(pydantic.BaseModel):
	hook_id :int
	hook :Hook
	zen :str|None = None
	repository :Repository
	sender :UserInfo

class PullRequest(pydantic.BaseModel):
	action :str
	number :int
	pull_request :PullRequestInfo
	repository :Repository
	sender :UserInfo
	before :str|None = None
	after :str|None = None

class Author(pydantic.BaseModel):
	name :str
	email :str

class HeadCommit(pydantic.BaseModel):
	id :str
	tree_id :str
	message :str
	timestamp :datetime.datetime
	author :Author
	committer :Author

class GithubJobEntry(pydantic.BaseModel):
	id :int
	name :str
	node_id :str
	head_branch :str
	head_sha :str
	path :str
	display_title :str
	event :str
	status :str
	conclusion :str
	check_suite_node_id :str
	url :str
	html_url :str
	created_at :str
	updated_at :str
	run_number :int
	workflow_id :int
	check_suite_id :int
	pull_requests :list
	actor :UserInfo
	run_attempt :int
	referenced_workflows :list
	run_started_at :datetime.datetime
	triggering_actor :UserInfo
	jobs_url :str
	logs_url :str
	check_suite_url :str
	artifacts_url :str
	cancel_url :str
	rerun_url :str
	workflow_url :str
	head_commit :HeadCommit
	repository :RepoInfo
	head_repository :RepoInfo
	previous_attempt_url :str|None = None

class GithubJobs(pydantic.BaseModel):
	total_count :int
	workflow_runs :typing.List[GithubJobEntry]

class JobStep(pydantic.BaseModel):
	name :str
	status :str
	conclusion :str
	number :int
	started_at :datetime.datetime
	completed_at :datetime.datetime

class WorkflowJobInfo(pydantic.BaseModel):
	id :int
	run_id :int
	run_attempt :int
	workflow_name :str
	head_branch :str
	run_url :str
	node_id :str
	head_sha :str
	url :str
	html_url :str
	status :str
	conclusion :str
	created_at :str
	started_at :str
	completed_at :str
	name :str
	steps :typing.List[JobStep]
	check_run_url :str
	labels :typing.List[str]
	runner_name :str | None = None
	runner_group_id :int | None = None
	runner_group_name :str | None = None
	runner_id :int | None = None

class WorkflowJob(pydantic.BaseModel):
	action :str
	workflow_job :WorkflowJobInfo
	repository :Repository
	sender :UserInfo