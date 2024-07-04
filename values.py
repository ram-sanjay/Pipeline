from aws_cdk import (
    Stack,
    App,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    aws_codebuild as codebuild,
    aws_imagebuilder as imagebuilder,
    aws_iam as iam,
    aws_ecr as ecr,
    aws_sns as sns,
    aws_s3 as s3,
    aws_ec2 as ec2,
)
import aws_cdk as cdk
from constructs import Construct
import json
from aws_cdk.aws_ec2 import IpAddresses

class PipelineStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        with open('tps.yaml', 'r') as yaml_file:
            tps_yaml_content = yaml_file.read()
        with open('tgsp.yaml', 'r') as yaml_file:
            tgsp_yaml_content = yaml_file.read()
            
        with open('config.json', 'r') as config_file:
            config = json.load(config_file)
        bucket_name=config.get('bucket')
        Site=config.get('Site')
        repo_url=config.get('repo_url')
        ecr_name = config.get('ecr-name')
        parameter1 = [config.get('parameter1')]
        parameter2 = [config.get('parameter2')]
        parameter3 = [config.get('parameter3')]
        vpc = config.get('vpc')
        subnet_id = config.get('subnet_id')
        tpsbaseami = config.get('tps-base-ami')
        tgspbaseami = config.get('tgsp-base-ami')
        KeysBucket = [config.get('KeysBucket')]
        PrivateKey = [config.get('PrivateKey')]
        PublicKey = [config.get('PublicKey')]
        TgspLogsBucket = [config.get('TgspLogsBucket')]
        TpsLogsBucket = [config.get('TpsLogsBucket')]

        existing_vpc = ec2.Vpc.from_lookup(
            self,
            "ExistingVPC",
            vpc_id=vpc,
        )
        security_group = ec2.SecurityGroup(
            self,
            "SSHSecurityGroup",
            vpc=existing_vpc,
            description="Allow SSH access",
            allow_all_outbound=True,
        )
        security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(22),
            "Allow SSH access from anywhere",
        )
        security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(443),
            "Allow SSH access from anywhere",
        )
        security_group_id = [security_group.security_group_id]

        TPS_component = imagebuilder.CfnComponent(
            self,
            "TPSComponent",
            name="TPS-component",
            platform="Linux",
            version="1.1.2",
            data=tps_yaml_content,
        )

        tps_distribution_config = imagebuilder.CfnDistributionConfiguration(
            self,
            "DistributionConfig",
            name="TPS-distribution-config",
            distributions=[
                imagebuilder.CfnDistributionConfiguration.DistributionProperty(
                    region="ap-south-1",
                    ami_distribution_configuration={
                        "name": "TPS-ubuntu-ami-{{ imagebuilder:buildDate }}"
                    }
                )
            ]
        )
   
        tps_recipe = imagebuilder.CfnImageRecipe(
            self,
            "TPSRecipe",
            name="TPS-recipe",
            parent_image=tpsbaseami,
            version="1.1.2",
            components=[
                imagebuilder.CfnImageRecipe.ComponentConfigurationProperty(
                    component_arn=TPS_component.attr_arn,
                    parameters=[
                        imagebuilder.CfnImageRecipe.ComponentParameterProperty(
                            name="InputParameter1",
                            value=parameter1
                        ),
                        imagebuilder.CfnImageRecipe.ComponentParameterProperty(
                            name="InputParameter2",
                            value=parameter2
                        ),
                        imagebuilder.CfnImageRecipe.ComponentParameterProperty(
                            name="KeysBucket",
                            value=KeysBucket
                        ),
                        imagebuilder.CfnImageRecipe.ComponentParameterProperty(
                            name="PrivateKey",
                            value=PrivateKey
                        ),
                        imagebuilder.CfnImageRecipe.ComponentParameterProperty(
                            name="PublicKey",
                            value=PublicKey
                        ),
                        imagebuilder.CfnImageRecipe.ComponentParameterProperty(
                            name="LogsBucket",
                            value=TpsLogsBucket
                        ),
                        imagebuilder.CfnImageRecipe.ComponentParameterProperty(
                            name="InputParameter3",
                            value=parameter3
                        )
                    ]
                )
            ],
        )
       
        role = iam.Role(
            self,
            "InstanceRole",
            role_name= "Pipeline_CDK",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("EC2InstanceProfileForImageBuilder"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AWSImageBuilderFullAccess"),
            ]
        )
        instance_profile_cdk = iam.CfnInstanceProfile(
            self,
            "InstanceProfile",
            instance_profile_name="Pipeline_CDK",
            roles=[role.role_name],
        )

        tps_infrastructure_config = imagebuilder.CfnInfrastructureConfiguration(
            self,
            "TPSInfrastructureConfig",
            name="TPS-infrastructure-config",
            instance_types=["t3.small"],
            subnet_id=subnet_id, 
            security_group_ids=security_group_id,
            instance_profile_name=instance_profile_cdk.instance_profile_name,
        )
        tps_infrastructure_config.add_depends_on(instance_profile_cdk)

        tps_pipeline = imagebuilder.CfnImagePipeline(
            self,
            "TPSPipeline",
            name="TPS-cdk-pipeline",
            image_recipe_arn=tps_recipe.ref,
            infrastructure_configuration_arn=tps_infrastructure_config.ref,
            distribution_configuration_arn=tps_distribution_config.ref,
            image_tests_configuration=imagebuilder.CfnImagePipeline.ImageTestsConfigurationProperty(
                image_tests_enabled=False
            )
        )

        TGSP_component = imagebuilder.CfnComponent(
            self,
            "TGSPComponent",
            name="TGSP-component",
            platform="Linux",
            version="1.1.2",
            data=tgsp_yaml_content,
        )

        # Create an Image Builder distribution configuration
        tgsp_distribution_config = imagebuilder.CfnDistributionConfiguration(
            self,
            "TGSPDistributionConfig",
            name="TGSP-distribution-config",
            distributions=[
                imagebuilder.CfnDistributionConfiguration.DistributionProperty(
                    region="ap-south-1",
                    ami_distribution_configuration={
                        "name": "TGSP-ubuntu-ami-{{ imagebuilder:buildDate }}"
                    }
                )
            ]
        )

        tgsp_recipe = imagebuilder.CfnImageRecipe(
            self,
            "TGSPRecipe",
            name="TGSP-recipe",
            parent_image=tgspbaseami,
            version="1.1.2",
            components=[
                imagebuilder.CfnImageRecipe.ComponentConfigurationProperty(
                    component_arn=TGSP_component.attr_arn,
                    parameters=[
                        imagebuilder.CfnImageRecipe.ComponentParameterProperty(
                            name="InputParameter1",
                            value=parameter1
                        ),
                        imagebuilder.CfnImageRecipe.ComponentParameterProperty(
                            name="InputParameter2",
                            value=parameter2
                        ),
                        imagebuilder.CfnImageRecipe.ComponentParameterProperty(
                            name="KeysBucket",
                            value=KeysBucket
                        ),
                        imagebuilder.CfnImageRecipe.ComponentParameterProperty(
                            name="PrivateKey",
                            value=PrivateKey
                        ),
                        imagebuilder.CfnImageRecipe.ComponentParameterProperty(
                            name="PublicKey",
                            value=PublicKey
                        ),
                        imagebuilder.CfnImageRecipe.ComponentParameterProperty(
                            name="LogsBucket",
                            value=TgspLogsBucket
                        ),
                        imagebuilder.CfnImageRecipe.ComponentParameterProperty(
                            name="InputParameter3",
                            value=parameter3
                        )
                    ]
                )
            ],
        )

        tgsp_infrastructure_config = imagebuilder.CfnInfrastructureConfiguration(
            self,
            "InfrastructureConfig",
            name="TGSP-infrastructure-config",
            instance_types=["t3.small"],
            subnet_id=subnet_id, 
            security_group_ids=security_group_id,
            instance_profile_name=instance_profile_cdk.instance_profile_name,
        )
        tgsp_infrastructure_config.add_depends_on(instance_profile_cdk)

        tgsp_pipeline = imagebuilder.CfnImagePipeline(
            self,
            "TGSPPipeline",
            name="TGSP-cdk-pipeline",
            image_recipe_arn=tgsp_recipe.ref,
            infrastructure_configuration_arn=tgsp_infrastructure_config.ref,
            distribution_configuration_arn=tgsp_distribution_config.ref,
            image_tests_configuration=imagebuilder.CfnImagePipeline.ImageTestsConfigurationProperty(
                image_tests_enabled=False
            )
        )

        ecr_repository = ecr.Repository.from_repository_name(
            self, "ECRRepository", repository_name=ecr_name,
        )
        custom_policy_statement = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "iam:CreateRole",
                "iam:PutRolePolicy",
                "iam:AttachRolePolicy",
                "iam:DetachRolePolicy",
                "iam:DeleteRolePolicy",
                "iam:DeleteRole",
                "iam:CreatePolicy",
                "iam:DeletePolicy",
                "iam:CreatePolicyVersion",
                "iam:DeletePolicyVersion",
                "iam:ListPolicyVersions",
                "iam:GetPolicy",
                "iam:GetPolicyVersion",
                "iam:ListAttachedRolePolicies",
                "iam:ListRolePolicies",
                "iam:GetRole",
                "iam:GetRolePolicy",
                "iam:PassRole",
                "ec2:*",
                "s3:*",
                "cloudformation:*",
                "ssm:*",
                "route53:*",
            ],
            resources=["*"],
        )

        codebuild_role = iam.Role(
            self,
            "CodeBuildRole",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchLogsFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess"),
            ],
        )
        codebuild_role.add_to_policy(custom_policy_statement)


        ami_creation = codebuild.Project(
            self,
            "AMICreation",
            project_name="AMI_Creation",
            description="CodeBuild project for AMI Creation",
            build_spec=codebuild.BuildSpec.from_asset("ami.yml"),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.AMAZON_LINUX_2_5,
                compute_type=codebuild.ComputeType.SMALL,
            ),
            role=iam.Role(
                self,
                "AMICreationServiceRole",
                assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
                managed_policies=[
                    iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess"),
                    iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMFullAccess"),
                    iam.ManagedPolicy.from_aws_managed_policy_name("AWSCodeBuildAdminAccess"),
                    iam.ManagedPolicy.from_aws_managed_policy_name("AWSImageBuilderFullAccess"),
                ],
            ),
        )
        ami_creation.apply_removal_policy(cdk.RemovalPolicy.DESTROY)

        e2e_check = codebuild.Project(
            self,
            "E2ECheck",
            project_name="E2E_Check",
            description="CodeBuild project For E2E Check",
            build_spec=codebuild.BuildSpec.from_asset("e2e.yml"),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.AMAZON_LINUX_2_5,
                compute_type=codebuild.ComputeType.SMALL,
            ),
            role=iam.Role(
                self,
                "E2EServiceRole",
                assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
                managed_policies=[
                    iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMFullAccess"),
                ],
            ),
        )
        e2e_check.apply_removal_policy(cdk.RemovalPolicy.DESTROY)


        cdk_deploy = codebuild.Project(
            self,
            "CDKDeploy",
            project_name="CDK_Deploy",
            description="CodeBuild project for CDK Deploy",
            build_spec=codebuild.BuildSpec.from_asset("cdk-deploy.yml"),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.from_ecr_repository(
                    repository=ecr_repository
                ),
                compute_type=codebuild.ComputeType.SMALL,
                privileged=True,
            ),
            role=codebuild_role,
        )
        cdk_deploy.apply_removal_policy(cdk.RemovalPolicy.DESTROY)

        post_deployment = codebuild.Project(
            self,
            "PostDeployment",
            project_name="Post_Deployment",
            description="CodeBuild project for Post Deployment Cleanup",
            build_spec=codebuild.BuildSpec.from_asset("post-deployment.yml"),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.from_ecr_repository(
                    repository=ecr_repository
                ),
                compute_type=codebuild.ComputeType.SMALL,
                privileged=True,
            ),
            role=codebuild_role,
        )
        post_deployment.apply_removal_policy(cdk.RemovalPolicy.DESTROY)


        bucket = s3.Bucket.from_bucket_name(self, "ImportedBucket", bucket_name )
        existing_topic_arn = config.get('existing_topic_arn')
        notification_topic = sns.Topic.from_topic_arn(
            self, "ExistingTopic",
            topic_arn=existing_topic_arn
        )
        variable1 = codepipeline.Variable(
            variable_name="TPS_IMAGE_BUILDER_PIPELINE_ARN",
            default_value=tps_pipeline.ref
        )
        variable2 = codepipeline.Variable(
            variable_name="TGSP_IMAGE_BUILDER_PIPELINE_ARN",
            default_value=tgsp_pipeline.ref
        )
        variable3 = codepipeline.Variable(
            variable_name="Site",
            default_value=Site
        )
        variable4 = codepipeline.Variable(
            variable_name="repo_url",
            default_value=repo_url
        )

        source_output = codepipeline.Artifact(artifact_name='source')

        pipeline = codepipeline.Pipeline(
            self, "Pipeline",
            pipeline_name="GSTNPipeline",
            variables=[variable1,variable2,variable3,variable4],
            artifact_bucket=bucket,
            pipeline_type=codepipeline.PipelineType.V2,
            # execution_mode=codepipeline.ExecutionMode.QUEUED,
            stages=[
                codepipeline.StageProps(
                    stage_name='Source',
                    actions=[
                        codepipeline_actions.S3SourceAction(
                            bucket=bucket,
                            bucket_key='config.zip',    
                            action_name='S3Source',
                            run_order=1,
                            output=source_output,
                            variables_namespace="SourceVariables"
                        ),
                    ]
                ),
                codepipeline.StageProps(
                    stage_name='AMI',
                    actions=[
                        codepipeline_actions.CodeBuildAction(
                            action_name='BuildImages',
                            input=source_output,
                            project=ami_creation,
                            run_order=1,
                            variables_namespace="AMI-ID",
                            environment_variables={
                                "TPS_IMAGE_BUILDER_PIPELINE_ARN":  codebuild.BuildEnvironmentVariable(value="#{variables.TPS_IMAGE_BUILDER_PIPELINE_ARN}"),
                                "TGSP_IMAGE_BUILDER_PIPELINE_ARN":  codebuild.BuildEnvironmentVariable(value="#{variables.TGSP_IMAGE_BUILDER_PIPELINE_ARN}"),
                            },
                        )
                    ]
                ),
                codepipeline.StageProps(
                    stage_name='Deploy',
                    actions=[
                        codepipeline_actions.CodeBuildAction(
                            action_name='CDKDeploy',
                            input=source_output,
                            project=cdk_deploy,
                            run_order=1,
                            environment_variables={
                                "tps_ami_id": codebuild.BuildEnvironmentVariable(value="#{AMI-ID.tps_ami_id}"),
                                "tgps_ami_id": codebuild.BuildEnvironmentVariable(value="#{AMI-ID.tgps_ami_id}"),
                                "repo_url": codebuild.BuildEnvironmentVariable(value="#{variables.repo_url}"),
                                "deploy_stack": codebuild.BuildEnvironmentVariable(value="#{variables.Site}"),
                                
                            },
                        )
                    ]
                ),
                codepipeline.StageProps(
                    stage_name='E2E_Check',
                    actions=[
                        codepipeline_actions.CodeBuildAction(
                            action_name='E2E',
                            input=source_output,
                            project=e2e_check,
                            run_order=1,
                            environment_variables={
                                "repo_url": codebuild.BuildEnvironmentVariable(value="#{variables.repo_url}"),
                                "Site": codebuild.BuildEnvironmentVariable(value="#{variables.Site}"),
                                
                            },
                        )
                    ]
                ),
                codepipeline.StageProps(
                    stage_name="Approve",
                    actions=[
                        codepipeline_actions.ManualApprovalAction(
                            action_name="ManualApproval",
                            notification_topic=notification_topic,
                        ),
                    ],
                ),
                codepipeline.StageProps(
                    stage_name='PostDeploymentCleanup',
                    actions=[
                        codepipeline_actions.CodeBuildAction(
                            action_name='PostDeployment',
                            input=source_output,
                            project=post_deployment,
                            run_order=1,
                            environment_variables={
                                "repo_url": codebuild.BuildEnvironmentVariable(value="#{variables.repo_url}"),
                                "site": codebuild.BuildEnvironmentVariable(value="#{variables.Site}"),
                                
                            },
                        )
                    ]
                )
            ]
        )


app = App()
with open('config.json', 'r') as config_file:
    config = json.load(config_file)
env = cdk.Environment(account=config.get('account_id'), region=config.get('region'))
PipelineStack(app, "PipelineStack", env=env)
app.synth()



,
    "KeysBucket":"tgsp-gs-prod-signingkeys",
    "PrivateKey":"gsp-qa-prv",
    "PublicKey":"gsp-qa-pub",
    "TpsLogsBucket":"tps-gs-signed-logs",
    "TgspLogsBucket":"tgsp-gs-signed-logs"